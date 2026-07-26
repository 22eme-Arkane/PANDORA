"""Conversion déterministe d'un Découpage PANDORA en plans Storyboard.

Le format courant est le contrat éditorial « DÉCOUPAGE PANDORA 2 » défini dans
``core.decoupage_document``. Les anciens formats Cinéma et Live restent importables
uniquement pour ne pas casser les projets existants ; ils ne doivent plus servir de
consigne de génération.

Format produit par api.live_extract.FormatConducteurWorker (mise en page Live/Mapping) :

    === ACTE {n} — {nom de l'acte} ===
    PLAN {n} — {titre}
    Durée : {x}s · Valeur de plan : {…} · Mouvement : {…}
    PROMPT VIDÉO (français) : "{prompt vidéo, possiblement multi-lignes}"
    PROMPT SON (sound design / SFX, français) : "{prompt son}"
"""

import re

from core.decoupage_document import (
    is_v2_document,
    parse_v2_document,
    validate_v2_document,
)

_ACTE_RE     = re.compile(r"^=+\s*(.*?)\s*=+\s*$")   # toute ligne « === … === » = frontière d'acte
_ACTE_NUM_RE = re.compile(r"^ACTE\s+(\d+)\s*[—–:.\-]?\s*(.*)$", re.IGNORECASE)
_PLAN_RE = re.compile(r"^PLAN\s+(\d+)\s*[—–:-]\s*(.*)$", re.IGNORECASE)
_DUR_RE  = re.compile(r"Dur[ée]{1,2}\s*:\s*(\d+)", re.IGNORECASE)
# Timecode « 0:20 », « 0'20 », « 1m10 » : le modèle bascule spontanément sur cette
# notation pour les plans longs. _DUR_RE n'attrapait que le chiffre de tête → un plan
# de 20 s devenait un plan de 0 SECONDE, en silence (constat Matthieu 2026-07-26).
_DUR_TC_RE = re.compile(
    r"Dur[ée]{1,2}\s*:\s*(\d+)\s*[:'’m]\s*(\d{1,2})(?!\d)", re.IGNORECASE)
# Secondes décimales « 0,5s » / « 0.5 s » : arrondies, jamais ramenées à zéro.
_DUR_DEC_RE = re.compile(r"Dur[ée]{1,2}\s*:\s*(\d+[.,]\d+)", re.IGNORECASE)


def duration_seconds(line: str) -> int | None:
    """Durée en secondes lue sur une ligne technique, ou None si illisible.

    Comprend « 12s », « 22 s », « 20 secondes », « 0:20 », « 0'20 », « 1m10 »,
    « 0,5s ». Ne renvoie JAMAIS 0 : une durée nulle est un plan qui n'existe pas.
    """
    text = line or ""
    m = _DUR_TC_RE.search(text)
    if m:
        total = int(m.group(1)) * 60 + int(m.group(2))
        return total or None
    m = _DUR_DEC_RE.search(text)
    if m:
        try:
            return max(1, round(float(m.group(1).replace(",", "."))))
        except ValueError:
            return None
    m = _DUR_RE.search(text)
    if m:
        return int(m.group(1)) or None
    return None
_VAL_RE  = re.compile(r"Valeur\s+de\s+plan\s*:\s*([^·|,;\n]+)", re.IGNORECASE)
_MOV_RE  = re.compile(r"Mouvement\s*:\s*([^·|,;\n]+)", re.IGNORECASE)
_VID_RE  = re.compile(r"^PROMPT\s+VID[EÉ]O[^:]*:\s*(.*)$", re.IGNORECASE)
_SON_RE  = re.compile(r"^PROMPT\s+SON[^:]*:\s*(.*)$", re.IGNORECASE)
# Ligne technique « Durée : … · Valeur de plan : … · Mouvement : … »
_TECH_RE = re.compile(r"^\s*(Dur[ée]{1,2}\s*:|Valeur\s+de\s+plan\s*:)", re.IGNORECASE)


def _strip_quotes(s: str) -> str:
    s = (s or "").strip()
    for a, b in (('"', '"'), ("«", "»"), ("“", "”"), ("'", "'")):
        if len(s) >= 2 and s.startswith(a) and s.endswith(b):
            return s[1:-1].strip()
    # guillemet ouvrant seul (prompt multi-lignes dont la fermeture a été concaténée) :
    if s.startswith(('"', "«", "“")):
        s = s[1:].strip()
    if s.endswith(('"', "»", "”")):
        s = s[:-1].strip()
    return s.strip()


# ── Lecteur de migration du format CINÉMA historique ──────────────────────────
# Le format compact ci-dessous n'est plus produit ni demandé. Il est reconnu une seule
# fois au chargement afin de convertir sans perte les anciens projets en fiches v2.
_CINE_PLAN_RE = re.compile(r"^P\s*0*(\d{1,3})\s*\|(.*)$", re.IGNORECASE)
# Les anciens projets utilisent « SEEDANCE ». Les nouveaux documents emploient
# le terme moteur-agnostique « PROMPT » ; les deux restent lisibles.
_CINE_PROMPT_RE = re.compile(
    r"^[\s→>»«\-–—]*(?:PROMPT(?:\s+VID[EÉ]O)?|SEEDANCE)\s*:\s*(.*)$",
    re.IGNORECASE,
)
_CINE_SEED_RE = _CINE_PROMPT_RE  # compatibilité pour les imports/tests historiques
_CINE_SEQ_RE  = re.compile(
    r"^[\s—–\-]*S[EÉ]QUENCE\s+(\d+)\s*[—–:.\-]?\s*(.*?)\s*[—–\-]*$", re.IGNORECASE)
_CINE_DUR_RE  = re.compile(r"~?\s*(\d+)\s*s", re.IGNORECASE)


def _is_cinema_layout(text: str) -> bool:
    """Ancien découpage Cinéma convertible en fiches v2 ?"""
    lines = [l.strip() for l in (text or "").splitlines()]
    if not any(_CINE_PLAN_RE.match(l) for l in lines):
        return False
    return any(_CINE_PROMPT_RE.match(l) for l in lines)


def _parse_cinema_segments(text: str) -> list:
    """Lit un ancien document Cinéma pour sa migration, sans appel IA."""
    segs: list = []
    cur = None
    act, act_name = 1, ""
    collecting = None   # "seedance" | None

    def _flush():
        nonlocal cur
        if cur is not None:
            segs.append(cur)
        cur = None

    for raw in (text or "").splitlines():
        s = raw.strip()
        if not s:
            continue
        mseq = _CINE_SEQ_RE.match(s)
        if mseq and ("séquence" in s.lower() or "sequence" in s.lower()):
            act = int(mseq.group(1))
            act_name = mseq.group(2).strip(" —–-.")
            collecting = None
            continue
        mp = _CINE_PLAN_RE.match(s)
        if mp:
            _flush()
            parts = [p.strip() for p in mp.group(2).split("|")]
            dur = 5
            if parts:
                md = _CINE_DUR_RE.search(parts[-1])
                if md:
                    dur = int(md.group(1))
            cur = {"act": act, "act_name": act_name, "action": "",
                   "number": int(mp.group(1)),
                   "duration": dur,
                   "shot_size":       parts[0] if len(parts) > 0 else "",
                   "camera_movement": parts[1] if len(parts) > 1 else "",
                   "camera_axis":     parts[2] if len(parts) > 2 else "",
                   "prompt": "", "sound_prompt": "", "_lines": []}
            collecting = None
            continue
        if cur is None:
            continue
        ms = _CINE_PROMPT_RE.match(s)
        if ms:
            cur["prompt"] = ms.group(1).strip()
            collecting = "seedance"
            continue
        if collecting == "seedance":
            cur["prompt"] = (cur["prompt"] + " " + s).strip()
        else:
            cur["_lines"].append(s)

    _flush()

    for seg in segs:
        seg["prompt"] = _strip_quotes(seg["prompt"])
        # Action (titre du plan) : on préfère une ligne de DESCRIPTION (ni l'en-tête
        # INT./EXT., ni un NOM PERSONNAGE tout-majuscules de dialogue) ; à défaut
        # l'INT./EXT. ; jamais vide.
        lines = seg.pop("_lines", [])
        seg["source"] = "\n".join(lines).strip()
        _is_loc = lambda l: bool(re.match(r"^(INT\.|EXT\.)", l, re.IGNORECASE))
        _is_speaker = lambda l: l.isupper() and len(l) <= 40
        desc = [l for l in lines if not _is_loc(l) and not _is_speaker(l)]
        loc  = [l for l in lines if _is_loc(l)]
        seg["action"] = (desc[0] if desc else
                         (loc[0] if loc else (lines[0] if lines else "")))
        if not seg["prompt"]:
            seg["prompt"] = seg.get("action", "")
    return segs


def _legacy_cinema_to_v2(text: str) -> str:
    """Migre un ancien découpage Cinéma vers les fiches éditoriales v2.

    Le lecteur historique n'est utilisé qu'ici afin de préserver les projets
    existants. Aucune de ces anciennes conventions n'est renvoyée au modèle IA.
    """
    segments = _parse_cinema_segments(text)
    if not segments:
        return (text or "").strip()
    lines = ["DÉCOUPAGE PANDORA 2"]
    previous_sequence = None
    for index, segment in enumerate(segments, 1):
        sequence = int(segment.get("act") or 1)
        if sequence != previous_sequence:
            title = str(segment.get("act_name") or "").strip()
            lines.extend(["", f"SÉQUENCE {sequence}" + (f" — {title}" if title else "")])
            previous_sequence = sequence
        duration = float(segment.get("duration") or 5)
        duration_label = str(int(duration)) if duration.is_integer() else str(duration).replace(".", ",")
        source = str(segment.get("source") or segment.get("action") or "").strip()
        prompt = str(segment.get("prompt") or source).strip()
        lines.extend([
            "",
            f"PLAN {index:02d}",
            f"SOURCE SCÉNARIO : {source}",
            "INTENTION : À préciser dans la coécriture du découpage.",
            "RYTHME : À préciser.",
            f"DURÉE : {duration_label}s",
            f"PROMPT VISUEL : {prompt}",
            "PERSONNAGES : —",
            "DÉCOR : —",
            "ACCESSOIRES : —",
            "VÉHICULES : —",
            "HMC : —",
            f"VALEUR PROPOSÉE : {segment.get('shot_size') or '—'}",
            f"AXE PROPOSÉ : {segment.get('camera_axis') or '—'}",
            f"MOUVEMENT PROPOSÉ : {segment.get('camera_movement') or '—'}",
            "FOCALE PROPOSÉE : —",
            "MOOD : À CRÉER",
        ])
    return "\n".join(lines).strip()


def is_structured_layout(text: str) -> bool:
    """La source est-elle déjà un Découpage PANDORA structuré ?

    Live : au moins un « PLAN n » ET un marqueur corroborant. Un ancien document
    Cinéma complet est encore reconnu le temps de sa migration automatique.
    Un conducteur brut vaguement numéroté (« Plan 1 : intro ») N'EST PAS une mise en
    page co-écrite → il garde le découpage IA, pas le parsing."""
    if not text:
        return False
    if is_v2_document(text):
        return True
    if _is_cinema_layout(text):
        return True
    lines = [l.strip() for l in text.splitlines()]
    n_plans = sum(1 for l in lines if _PLAN_RE.match(l))
    if n_plans < 1:
        return False
    return any(_VID_RE.match(l) or _TECH_RE.match(l) for l in lines)


def canonicalize_layout(text: str) -> str:
    """Normalise le format courant et migre les anciens découpages Cinéma.

    Le format v2 reste strictement intact. Un ancien format Cinéma complet est converti
    en fiches v2 ; les autres documents (notamment Live) restent inchangés, avec le seul
    nom d'un ancien fournisseur remplacé par le terme neutre PROMPT.
    """
    value = (text or "").strip()
    if is_v2_document(value):
        return value
    if _is_cinema_layout(value):
        return _legacy_cinema_to_v2(value)
    out = []
    for raw in value.splitlines():
        match = _CINE_PROMPT_RE.match(raw.strip())
        if match:
            out.append("→ PROMPT: " + match.group(1).strip())
        else:
            out.append(raw.rstrip())
    return "\n".join(out).strip()


def validate_layout(text: str) -> list[str]:
    """Retourne les erreurs bloquantes d'un découpage structuré."""
    if is_v2_document(text):
        return validate_v2_document(text)
    if not is_structured_layout(text):
        return ["structure_non_reconnue"]
    segments = parse_layout_segments(text)
    if not segments:
        return ["aucun_plan"]
    errors: list[str] = []
    for index, segment in enumerate(segments, 1):
        try:
            duration = float(segment.get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0
        if duration < 2 or duration > 15:
            errors.append(f"P{index:02d}:duree")
        if not str(segment.get("prompt") or "").strip():
            errors.append(f"P{index:02d}:prompt")
    return errors


def parse_layout_segments(layout_text: str) -> list:
    """Parse un Découpage PANDORA en segments bruts (à passer ensuite à _normalize).

    Chaque segment : {act, act_name, action, duration, shot_size, camera_movement,
    prompt, sound_prompt} (+ camera_axis en Cinéma). Robuste aux prompts multi-lignes,
    à un préfixe éventuel (timeline musicale) et aux petites variations de casse/
    ponctuation. Le format compact Cinéma n'est accepté que pour migrer un ancien projet."""
    if is_v2_document(layout_text):
        return parse_v2_document(layout_text)
    if _is_cinema_layout(layout_text):
        return _parse_cinema_segments(layout_text)
    segs: list = []
    cur = None
    act, act_name = 1, ""
    _acte_auto = 1      # numéro d'acte auto quand l'en-tête n'en fournit pas
    collecting = None   # "video" | "sound" | None

    def _flush():
        nonlocal cur
        if cur is not None:
            segs.append(cur)
        cur = None

    for raw in (layout_text or "").splitlines():
        s = raw.strip()
        if not s:
            # Ligne vide : n'INTERROMPT PAS un prompt multi-paragraphes en cours de collecte
            # (l'utilisateur aère souvent ses prompts à la main). Seules les lignes
            # STRUCTURELLES ci-dessous cassent la collecte.
            continue
        # En-tête d'acte : TOUTE ligne « === … === » (frontière structurelle, jamais avalée
        # par un prompt). Numéro extrait si présent, sinon auto-incrémenté (« === FINAL === »).
        m = _ACTE_RE.match(s)
        if m and s.startswith("="):
            content = m.group(1).strip()
            mn = _ACTE_NUM_RE.match(content)
            if mn:
                act = int(mn.group(1))
                act_name = mn.group(2).strip(" —–-.")
                _acte_auto = act + 1
            else:
                act = _acte_auto
                _acte_auto += 1
                act_name = re.sub(r"^ACTE\b\s*", "", content, flags=re.IGNORECASE).strip(" —–-.")
            collecting = None
            continue
        m = _PLAN_RE.match(s)
        if m:
            _flush()
            cur = {"act": act, "act_name": act_name, "action": m.group(2).strip(),
                   "duration": 5, "shot_size": "", "camera_movement": "",
                   "prompt": "", "sound_prompt": ""}
            collecting = None
            continue
        if cur is None:
            continue   # avant le 1er plan (préfixe / timeline musicale) → ignoré
        if _TECH_RE.match(s):
            md = duration_seconds(s)
            if md:
                cur["duration"] = md
            mv = _VAL_RE.search(s)
            if mv:
                cur["shot_size"] = mv.group(1).strip(" ·|")
            mm = _MOV_RE.search(s)
            if mm:
                cur["camera_movement"] = mm.group(1).strip(" ·|")
            collecting = None
            continue
        m = _VID_RE.match(s)
        if m:
            cur["prompt"] = m.group(1).strip()
            collecting = "video"
            continue
        m = _SON_RE.match(s)
        if m:
            cur["sound_prompt"] = m.group(1).strip()
            collecting = "sound"
            continue
        # Ligne de continuation d'un prompt multi-lignes.
        if collecting == "video":
            cur["prompt"] = (cur["prompt"] + " " + s).strip()
        elif collecting == "sound":
            cur["sound_prompt"] = (cur["sound_prompt"] + " " + s).strip()

    _flush()

    for seg in segs:
        seg["prompt"] = _strip_quotes(seg["prompt"])
        seg["sound_prompt"] = _strip_quotes(seg["sound_prompt"])
        # Repli : un plan sans PROMPT VIDÉO reprend au moins son titre (jamais vide).
        if not seg["prompt"]:
            seg["prompt"] = seg["action"]
    return segs


def layout_segments_to_cinema_shots(layout_text: str) -> list:
    """Segments de la Mise en page PANDORA → plans STORYBOARD Cinéma (mêmes clés que
    le découpage IA de api.screenplay.GenerateStoryboardWorker). Prompts co-écrits
    repris TELS QUELS — c'est tout l'intérêt du chemin déterministe. Les champs
    caméra que la mise en page ne porte pas (focale, décor, acteurs, axe, heure…)
    restent vides : ils se complètent dans le Storyboard et les pages Mise en scène."""
    shots = []
    try:
        from core.visual_context import load_catalogs
        _catalogs = load_catalogs()
    except Exception:
        _catalogs = {"characters": [], "decors": [], "accessories": [],
                     "hmc": [], "vehicles": []}
    for i, seg in enumerate(parse_layout_segments(layout_text), 1):
        if not isinstance(seg, dict):
            continue
        try:
            _dur = min(float(seg.get("duration") or 8.0), 15.0)   # plafond Seedance
        except (TypeError, ValueError):
            _dur = 8.0
        shot = {
            "number":          i,
            "scene_title":     seg.get("intention") or seg.get("action", ""),
            "shot_size":       seg.get("shot_size", ""),
            "camera_movement": seg.get("camera_movement", ""),
            "camera_axis":     seg.get("camera_axis", ""),
            "focal":           seg.get("focal", ""),
            "duration":        _dur,
            "seedance_prompt": seg.get("prompt", ""),
            "sound_prompt":    seg.get("sound_prompt", ""),
            "seq_num":         seg.get("act", 1),
            "seq_name":        seg.get("act_name", ""),
            "character_ids":   [],
            "character_names": list(seg.get("character_names") or []),
            "accessory_ids":   [],
            "accessory_names": list(seg.get("accessory_names") or []),
            "decor_id":        "",
            "decor_name":      seg.get("decor_name", ""),
            "vehicle_ids":     [],
            "vehicle_names":   list(seg.get("vehicle_names") or []),
            "hmc_ids":         [],
            "hmc_names":       list(seg.get("hmc_names") or []),
            "merged":          False,
            "merged_note":     "",
            # Transport narratif (2026-07-23) : l'extrait exact du scénario, le
            # rythme et l'intention de la fiche survivent désormais jusqu'au
            # composeur de prompt (bloc « narrative » de la bible visuelle).
            "source_excerpt":  seg.get("source", ""),
            "rhythm":          seg.get("rhythm", ""),
            "intention":       seg.get("intention", ""),
        }
        try:
            from core.visual_context import enrich_shot_entities
            enrich_shot_entities(shot, _catalogs)
        except Exception:
            pass
        # Le texte co-écrit reste intact dans ACTION. Les sections supplémentaires
        # sont exclusivement déterministes : titre/entités et champs caméra. Elles
        # permettent au composeur Seedance de reconnaître aussi ce chemin de découpage.
        try:
            from core.prompt_sections import (build as _build_sections,
                                               is_structured as _is_structured_prompt,
                                               technique_line)
            if not _is_structured_prompt(shot["seedance_prompt"]):
                entities = ", ".join(shot.get("character_names") or [])
                staging = (f"Personnages visibles : {entities}." if entities
                           else (shot.get("scene_title") or "Action du plan inchangée."))
                decor = shot.get("decor_name", "")
                technique = technique_line(shot) or f"Durée prévue : {_dur:g} secondes."
                shot["seedance_prompt"] = _build_sections(
                    action=seg.get("prompt", ""), staging=staging,
                    decor=decor, technique=technique,
                    sound=seg.get("sound_prompt", ""))
        except Exception:
            pass
        shots.append(shot)
    return shots
