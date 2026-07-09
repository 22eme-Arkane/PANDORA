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


def is_structured_layout(text: str) -> bool:
    """La source est-elle déjà une Mise en page PANDORA découpée en plans ?

    Exige au moins un « PLAN n » ET un marqueur CORROBORANT (« PROMPT VIDÉO » ou une ligne
    technique « Durée : … ») : un conducteur brut vaguement numéroté (« Plan 1 : intro »)
    N'EST PAS une mise en page co-écrite → il doit garder le découpage IA, pas le parsing."""
    if not text:
        return False
    lines = [l.strip() for l in text.splitlines()]
    n_plans = sum(1 for l in lines if _PLAN_RE.match(l))
    if n_plans < 1:
        return False
    return any(_VID_RE.match(l) or _TECH_RE.match(l) for l in lines)


def parse_layout_segments(layout_text: str) -> list:
    """Parse une Mise en page PANDORA en segments BRUTS (à passer ensuite à _normalize).

    Chaque segment : {act, act_name, action, duration, shot_size, camera_movement,
    prompt, sound_prompt}. Robuste aux prompts multi-lignes, à un préfixe éventuel
    (timeline musicale) et aux petites variations de casse/ponctuation."""
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
