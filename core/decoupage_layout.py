"""Conversion DÉTERMINISTE d'une « Mise en page PANDORA » (déjà découpée en plans) en
segments de découpage, SANS repasser par l'IA.

Quand l'utilisateur génère le découpage depuis la Mise en page PANDORA, celle-ci contient
DÉJÀ N plans co-écrits (« PLAN n — … » + PROMPT VIDÉO / PROMPT SON). Les re-soumettre à
Claude (a) TRONQUAIT la sortie (16000 tokens → 29 plans réduits à 17) et (b) jetait le
travail de co-écriture en re-générant les prompts. On parse donc directement la mise en
page : 1 plan = 1 segment, prompts REPRIS tels quels, zéro perte, zéro coût IA.

Format produit par api.live_extract.FormatConducteurWorker (mise en page Live/Mapping) :

    === ACTE {n} — {nom de l'acte} ===
    PLAN {n} — {titre}
    Durée : {x}s · Valeur de plan : {…} · Mouvement : {…}
    PROMPT VIDÉO (français) : "{prompt vidéo, possiblement multi-lignes}"
    PROMPT SON (sound design / SFX, français) : "{prompt son}"
"""

import re

_ACTE_RE     = re.compile(r"^=+\s*(.*?)\s*=+\s*$")   # toute ligne « === … === » = frontière d'acte
_ACTE_NUM_RE = re.compile(r"^ACTE\s+(\d+)\s*[—–:.\-]?\s*(.*)$", re.IGNORECASE)
_PLAN_RE = re.compile(r"^PLAN\s+(\d+)\s*[—–:-]\s*(.*)$", re.IGNORECASE)
_DUR_RE  = re.compile(r"Dur[ée]{1,2}\s*:\s*(\d+)", re.IGNORECASE)
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


# ── Format CINÉMA (FormatPandoraWorker / _FORMAT_PANDORA) ─────────────────────
# Deux formats de Mise en page PANDORA coexistent (cf. core/plan_layout.py) :
#   - Live   : « PLAN 1 — Titre » + « PROMPT VIDÉO … » (géré par les regex ci-dessus) ;
#   - Cinéma : « P01 | Valeur | Mouvement | Axe | ~Durée » + « → SEEDANCE: … ».
# Le déterministe (1 plan = 1 plan, prompts co-écrits REPRIS tels quels) doit marcher
# pour LES DEUX — sinon la mise en page Cinéma repart en réécriture IA (perte du travail).
_CINE_PLAN_RE = re.compile(r"^P\s*0*(\d{1,3})\s*\|(.*)$", re.IGNORECASE)
_CINE_SEED_RE = re.compile(r"^[\s→>»«\-–—]*SEEDANCE\s*:\s*(.*)$", re.IGNORECASE)
_CINE_SEQ_RE  = re.compile(
    r"^[\s—–\-]*S[EÉ]QUENCE\s+(\d+)\s*[—–:.\-]?\s*(.*?)\s*[—–\-]*$", re.IGNORECASE)
_CINE_DUR_RE  = re.compile(r"~?\s*(\d+)\s*s", re.IGNORECASE)


def _is_cinema_layout(text: str) -> bool:
    """Mise en page au format CINÉMA (« P01 | … » + « → SEEDANCE: … ») ?"""
    lines = [l.strip() for l in (text or "").splitlines()]
    if not any(_CINE_PLAN_RE.match(l) for l in lines):
        return False
    return any(_CINE_SEED_RE.match(l) for l in lines)


def _parse_cinema_segments(text: str) -> list:
    """Parse une Mise en page PANDORA au format CINÉMA en segments bruts (mêmes clés
    que le parseur Live + `camera_axis`). Prompt vidéo = ligne « → SEEDANCE: … »
    (multi-lignes tolérées), repris tel quel — c'est tout l'intérêt du déterministe."""
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
                   "duration": dur,
                   "shot_size":       parts[0] if len(parts) > 0 else "",
                   "camera_movement": parts[1] if len(parts) > 1 else "",
                   "camera_axis":     parts[2] if len(parts) > 2 else "",
                   "prompt": "", "sound_prompt": "", "_lines": []}
            collecting = None
            continue
        if cur is None:
            continue
        ms = _CINE_SEED_RE.match(s)
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
        _is_loc = lambda l: bool(re.match(r"^(INT\.|EXT\.)", l, re.IGNORECASE))
        _is_speaker = lambda l: l.isupper() and len(l) <= 40
        desc = [l for l in lines if not _is_loc(l) and not _is_speaker(l)]
        loc  = [l for l in lines if _is_loc(l)]
        seg["action"] = (desc[0] if desc else
                         (loc[0] if loc else (lines[0] if lines else "")))
        if not seg["prompt"]:
            seg["prompt"] = seg.get("action", "")
    return segs


def is_structured_layout(text: str) -> bool:
    """La source est-elle déjà une Mise en page PANDORA découpée en plans (Live OU
    Cinéma) ?

    Live : au moins un « PLAN n » ET un marqueur CORROBORANT (« PROMPT VIDÉO » ou une
    ligne technique « Durée : … »). Cinéma : au moins un « P01 | … » ET un « → SEEDANCE: ».
    Un conducteur brut vaguement numéroté (« Plan 1 : intro ») N'EST PAS une mise en
    page co-écrite → il garde le découpage IA, pas le parsing."""
    if not text:
        return False
    if _is_cinema_layout(text):
        return True
    lines = [l.strip() for l in text.splitlines()]
    n_plans = sum(1 for l in lines if _PLAN_RE.match(l))
    if n_plans < 1:
        return False
    return any(_VID_RE.match(l) or _TECH_RE.match(l) for l in lines)


def parse_layout_segments(layout_text: str) -> list:
    """Parse une Mise en page PANDORA en segments BRUTS (à passer ensuite à _normalize).

    Chaque segment : {act, act_name, action, duration, shot_size, camera_movement,
    prompt, sound_prompt} (+ camera_axis en Cinéma). Robuste aux prompts multi-lignes,
    à un préfixe éventuel (timeline musicale) et aux petites variations de casse/
    ponctuation. Dispatch automatique Cinéma (« P01 | … ») / Live (« PLAN n — … »)."""
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
            md = _DUR_RE.search(s)
            if md:
                cur["duration"] = int(md.group(1))
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
    for i, seg in enumerate(parse_layout_segments(layout_text), 1):
        if not isinstance(seg, dict):
            continue
        try:
            _dur = min(float(seg.get("duration") or 8.0), 15.0)   # plafond Seedance
        except (TypeError, ValueError):
            _dur = 8.0
        shots.append({
            "number":          i,
            "scene_title":     seg.get("action", ""),
            "shot_size":       seg.get("shot_size", ""),
            "camera_movement": seg.get("camera_movement", ""),
            "camera_axis":     seg.get("camera_axis", ""),
            "duration":        _dur,
            "seedance_prompt": seg.get("prompt", ""),
            "sound_prompt":    seg.get("sound_prompt", ""),
            "seq_num":         seg.get("act", 1),
            "seq_name":        seg.get("act_name", ""),
            "character_ids":   [],
            "accessory_ids":   [],
            "decor_id":        "",
            "merged":          False,
            "merged_note":     "",
        })
    return shots
