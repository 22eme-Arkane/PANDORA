"""
core/live_bar.py — Grammaire de prompt PANDORA | LIVE (mapping sur façade).

Spécification Matthieu du 2026-07-26. Ce n'est PAS une variante de la grammaire
Cinéma : sur quatre points elle en est l'inverse exact.

    ┌────────┬──────────────────────┬──────────────────────────────────────────┐
    │        │ Cinéma               │ Live / Mapping                           │
    ├────────┼──────────────────────┼──────────────────────────────────────────┤
    │ Caméra │ champ primaire       │ VERROUILLÉE, jamais nommée — la « caméra »│
    │        │ mouvement recherché  │ c'est le vidéoprojecteur, il est boulonné │
    │ Noir   │ valeur esthétique    │ valeur STRUCTURELLE : zéro lumière projetée│
    │ Durée  │ libre (4–15 s)       │ IMPOSÉE par la grille — 8 temps à X BPM   │
    │ Son    │ généré avec l'image  │ JAMAIS généré — le son, c'est le set      │
    └────────┴──────────────────────┴──────────────────────────────────────────┘

Conséquence directe : le vocabulaire de plateau qui fait la qualité d'un prompt
Cinéma est, en mapping, une LISTE DE DÉFAUTS À INTERDIRE.

Structure en dix blocs, dont DEUX ne partent jamais dans le payload :

    [🔒 VERROU]         constante — jamais éditée au plan
    [🏛️ SURFACE]        géométrie réelle : volumes, ouvertures, matériau
    [⏹️ ÉTAT 0]         l'image au temps 1 — un état, pas une action
    [🌀 TRANSFORMATION] le processus qui court sur la barre — UN seul, continu
    [⏺️ ÉTAT 1]         l'image au temps 8 — l'état d'arrivée
    [⬛ NOIR]           ce qui doit rester à zéro lumière
    [🎨 STYLE]          le style VJ (core/vj_styles.py)
    [🚫 CONTRAINTES]    les négatifs, dont toute la liste « anti-Cinéma »
    ───────────────────── frontière du payload ─────────────────────
    [🎼 GRILLE]         BPM · temps · sparkline — PANDORA et l'IA d'écriture SEULS
    [🎵 SOUND DESIGN]   documentation de set — jamais envoyé à un moteur d'image

Ce qui est sous la ligne sert à ÉCRIRE le prompt, jamais à le REMPLIR.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── §7 — Le vocabulaire Cinéma à bannir ──────────────────────────────────────
# Négatifs injectés systématiquement : chacun de ces artefacts est, projeté sur
# de la pierre, un DÉFAUT visible.
MAPPING_NEGATIVES = [
    "no camera movement", "no zoom", "no push in", "no pan", "no tilt",
    "no parallax", "no depth of field", "no bokeh", "no rack focus",
    "no lens flare", "no film grain", "no vignette", "no atmospheric haze",
    "no fog", "no volumetric light rays", "no background gradient",
    "no cuts", "no scene change", "no handheld shake",
]

# Les trois qui comptent le plus (§3) — toujours en tête, un modèle suit mieux
# le début d'une liste longue.
_CRITICAL_NEGATIVES = ["no atmospheric haze", "no fog", "no cuts",
                       "no scene change", "no film grain"]

# Termes POSITIFS bannis. Les quatre derniers sont des boosters sans effet ; les
# trois premiers sont activement contre-productifs en mapping (ils tirent vers la
# profondeur de champ simulée, le flare, le grain — des défauts sur une façade).
BANNED_POSITIVES = [
    "cinematic", "cinematographic", "cinématographique",
    "4K", "8K", "ultra-detailed", "ultra-détaillé", "masterpiece",
    "photorealistic", "photoréaliste",
]

_BANNED_RE = re.compile(
    r"(?<![A-Za-zÀ-ÿ0-9])(?:" +
    "|".join(re.escape(w) for w in sorted(BANNED_POSITIVES, key=len, reverse=True)) +
    r")(?![A-Za-zÀ-ÿ0-9])", re.IGNORECASE)

# Sparkline librosa : aucun moteur ne la lit, c'est du bruit de tokenisation.
_SPARK_RE = re.compile(r"[▁▂▃▄▅▆▇█]+")
_EMOJI_TAG_RE = re.compile(r"\[[^\]]*\]")


def sanitize_payload(text: str) -> tuple:
    """Nettoie un texte destiné au moteur. Retourne (texte, termes_bannis_retirés).

    Retire les étiquettes de bloc, la sparkline et les boosters contre-productifs.
    Ne réécrit RIEN d'autre : le texte de l'auteur passe mot pour mot.
    """
    out = _EMOJI_TAG_RE.sub(" ", text or "")
    out = _SPARK_RE.sub(" ", out)
    removed = sorted({m.group(0).lower() for m in _BANNED_RE.finditer(out)})
    out = _BANNED_RE.sub("", out)
    # Une SUITE de virgules (« sharp, , , . » après retrait de trois boosters
    # consécutifs) se collapse d'un coup : « \s*,\s*,+ » n'en mangeait que deux
    # sur trois et laissait « sharp,,. ».
    out = re.sub(r"(?:\s*,)+", ",", out)
    out = re.sub(r"\s+([,.;:])", r"\1", out)
    out = re.sub(r"[,;:]\s*(?=[.!?])", "", out)
    out = re.sub(r"[\s,;:]+$", "", out.strip())
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.strip(), removed


def bar_duration(bpm: float, beats: int = 8) -> float:
    """Durée EXACTE d'une barre, en secondes. 8 temps → 480 / BPM."""
    return (beats * 60.0 / bpm) if bpm else 0.0


def api_duration(bpm: float, beats: int = 8) -> str:
    """Durée envoyée au moteur : l'entier le PLUS PROCHE, jamais la valeur exacte.

    Aucun moteur du catalogue n'accepte de paramètre de tempo. La valeur exacte
    vit dans le conducteur et dans Resolume, qui conforme au BPM ; à 118 BPM
    l'écart est de 68 ms, soit 1,6 image à 24 fps — invisible sur une barre.
    """
    return str(max(1, round(bar_duration(bpm, beats))))


def duration_drift(bpm: float, beats: int = 8) -> float:
    """Écart (secondes, signé) entre la durée envoyée et la durée réelle."""
    exact = bar_duration(bpm, beats)
    return (float(api_duration(bpm, beats)) - exact) if exact else 0.0


# BPM qui tombent JUSTE sur 8 temps — à préférer quand le tempo est libre.
EXACT_BPM = {60: 8, 80: 6, 96: 5, 120: 4}


# ── §6 — La sparkline choisit la FORME du prompt, elle n'y figure jamais ─────
def transformation_family(sparkline: str) -> str:
    """Famille de TRANSFORMATION déduite de la courbe d'énergie.

    « flat » prolifération lente, tension tenue ; « rising » densification vers le
    pic ; « falling » retrait, la pierre réapparaît ; « drop » RUPTURE d'état —
    et celle-là ne se fait PAS en interpolation continue : il faut deux clips
    déclenchés dans Resolume, ou un multi_prompt en deux segments.
    """
    s = (sparkline or "").strip()
    if not s:
        return "flat"
    levels = [ord(c) - 0x2581 for c in s if 0x2581 <= ord(c) <= 0x2588]
    if not levels:
        return "flat"
    lo, hi = min(levels), max(levels)
    if hi - lo <= 1:
        return "flat"
    # Un pic isolé (montée puis retour) = rupture, pas une progression.
        # (détecté avant les monotonies : une seule barre haute n'est ni l'un ni l'autre)
    pic = levels.index(hi)
    if 0 < pic < len(levels) - 1 and levels[-1] - lo <= 1 and levels[0] - lo <= 1:
        return "drop"
    if levels[-1] > levels[0]:
        return "rising"
    if levels[-1] < levels[0]:
        return "falling"
    return "flat"


NEEDS_TWO_CLIPS = "drop"   # ne se rend pas en une passe I2V


# ── Les 8 blocs DANS le champ PROMPT VISUEL ──────────────────────────────────
# Décision 2026-07-27 : les blocs ne sont PAS déclarés dans core/decoupage_document
# (contrat partagé avec le Cinéma). Ils vivent comme sous-lignes étiquetées à
# l'INTÉRIEUR de PROMPT VISUEL, que `_field()` lit jusqu'au prochain libellé CONNU.
# Un libellé inconnu n'en est pas un : les sous-lignes restent donc dans le champ,
# intactes, et le Cinéma ne voit jamais rien de tout ceci.
#
# C'est aussi ce qui protège la détection : `is_v2_document` exige littéralement une
# ligne « PROMPT VISUEL : ». La remplacer par les blocs ferait retomber tout le Live
# sur les branches héritées — et chaque découpage repartirait en réécriture IA, en
# silence.
BLOCK_LABELS = {
    "surface":        ("SURFACE",),
    "state_0":        ("ÉTAT 0", "ETAT 0", "STATE 0"),
    "transformation": ("TRANSFORMATION",),
    "state_1":        ("ÉTAT 1", "ETAT 1", "STATE 1"),
    "black":          ("NOIR", "BLACK"),
    "style":          ("STYLE",),
    "constraints":    ("CONTRAINTES", "CONSTRAINTS"),
}

_ALL_BLOCK_RE = re.compile(
    r"^[ \t]*(?:" + "|".join(
        re.escape(a) for al in BLOCK_LABELS.values() for a in al) + r")[ \t]*:",
    re.IGNORECASE | re.MULTILINE)


def parse_blocks(text: str) -> dict:
    """Extrait les blocs LIVE d'un champ PROMPT VISUEL. {} si aucun.

    Tolérant : un découpage écrit avant ce contrat, ou un plan que l'utilisateur a
    réécrit en prose libre, ne rend rien — l'appelant retombe alors sur le texte
    entier. On ne casse jamais un plan existant.
    """
    src = text or ""
    out = {}
    for key, aliases in BLOCK_LABELS.items():
        alt = "|".join(re.escape(a) for a in aliases)
        m = re.search(rf"^[ \t]*(?:{alt})[ \t]*:[ \t]*(.*)$", src,
                      re.IGNORECASE | re.MULTILINE)
        if not m:
            continue
        nxt = _ALL_BLOCK_RE.search(src, m.end())
        val = src[m.start(1):(nxt.start() if nxt else len(src))]
        val = " ".join(val.split()).strip(" —-;,")
        if val:
            out[key] = val
    return out


def format_blocks(blocks: dict) -> str:
    """Rend les blocs sous la forme attendue dans PROMPT VISUEL (ordre imposé)."""
    lines = []
    for key, aliases in BLOCK_LABELS.items():
        val = " ".join(str((blocks or {}).get(key, "") or "").split())
        if val:
            lines.append(f"{aliases[0]} : {val}")
    return "\n".join(lines)


def has_blocks(text: str) -> bool:
    """Vrai si ce prompt porte au moins l'ossature d'une barre (les trois temps)."""
    b = parse_blocks(text)
    return bool(b.get("state_0") and b.get("transformation") and b.get("state_1"))


def bpm_of_track(name: str, tracks) -> float:
    """BPM du morceau nommé. 0.0 si inconnu — jamais d'exception."""
    try:
        tk = next((t for t in (tracks or [])
                   if isinstance(t, dict) and t.get("name") == name), None)
        return float((tk or {}).get("bpm") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def shot_extras(seg: dict, bpm: float = 0.0) -> dict:
    """Clés LIVE à poser sur un plan enregistré. {} si rien à ajouter.

    UNE seule fonction pour les DEUX points d'écriture des plans (le chemin
    « Appliquer le découpage » et le chemin Séquences). Le mode de panne à éviter
    est connu : n'enrichir qu'un des deux crée une perte à 100 % sur l'autre,
    silencieuse — c'est exactement ce qui était arrivé avec decoupage_content /
    layout_content. En passant par ici, les deux ne peuvent plus diverger.

    `duration_exact` est la durée VRAIE de la barre : on prend le nombre entier de
    temps le plus proche de la durée conformée, et on le reconvertit en secondes.
    C'est cette valeur — et pas l'entier — que le recalage ffmpeg attend.
    """
    out = {}
    blocks = parse_blocks(str(seg.get("prompt") or ""))
    if blocks:
        out["live_bar"] = blocks
    try:
        dur = float(seg.get("duration") or 0)
    except (TypeError, ValueError):
        dur = 0.0
    bpm = float(bpm or 0.0)
    if bpm > 0 and dur > 0:
        beats = max(1, round(dur * bpm / 60.0))
        out["beats"] = int(beats)
        out["bpm"] = round(bpm, 2)
        out["duration_exact"] = round(bar_duration(bpm, beats), 3)
    return out


@dataclass
class LiveBar:
    """Une barre de mapping : 8 blocs de payload, 4 champs hors payload."""

    # ── payload ──────────────────────────────────────────────────────────────
    surface: str = ""
    state_0: str = ""
    transformation: str = ""          # UN processus continu
    state_1: str = ""
    black: str = ""
    style: str = ""                   # ← core/vj_styles.py
    constraints: list = field(default_factory=list)

    # ── hors payload — sert à ÉCRIRE le prompt, jamais à le remplir ──────────
    bpm: float = 0.0
    beats: int = 8
    sparkline: str = ""
    sound_design: str = ""

    @property
    def exact_duration(self) -> float:
        return bar_duration(self.bpm, self.beats)

    @property
    def api_duration(self) -> str:
        return api_duration(self.bpm, self.beats)

    @property
    def family(self) -> str:
        return transformation_family(self.sparkline)

    @property
    def needs_two_clips(self) -> bool:
        """Un drop en milieu de barre ne s'interpole pas : il se coupe."""
        return self.family == NEEDS_TWO_CLIPS

    def to_prompt(self) -> tuple:
        """Prose envoyée au moteur. Retourne (prompt, termes_bannis_retirés).

        Le SON et la GRILLE ne sont JAMAIS concaténés — c'est la frontière du
        payload. Les négatifs anti-Cinéma sont injectés systématiquement, les
        trois plus importants en tête.
        """
        blocs = []
        if self.surface:
            blocs.append(f"Locked-off frontal view of {self.surface.strip().rstrip('.')}, "
                         "dead centre, filling the frame, isolated on pure black.")
        if self.state_0:
            blocs.append(f"At the first beat, {self.state_0.strip().rstrip('.')}.")
        if self.transformation:
            blocs.append(f"Across the shot, {self.transformation.strip().rstrip('.')}. "
                         "This is the only movement anywhere in frame.")
        if self.state_1:
            blocs.append(f"By the final instant, {self.state_1.strip().rstrip('.')}.")
        if self.black:
            blocs.append(f"Black: {self.black.strip().rstrip('.')}.")
        if self.style:
            blocs.append(f"Style: {self.style.strip().rstrip('.')}.")

        negs = list(_CRITICAL_NEGATIVES)
        for n in MAPPING_NEGATIVES + [c for c in self.constraints if c]:
            if n not in negs:
                negs.append(n)
        blocs.append("Constraints: " + ", ".join(negs) + ".")

        return sanitize_payload("\n\n".join(blocs))

    def to_params(self, image_url: str = "", end_image_url: str = "") -> dict:
        """Paramètres moteur. `end_image_url` est la MÉTHODE DEUX PLAQUES : sans
        elle, « le gel s'épaissit lentement » ne dit rien au modèle sur où il doit
        être arrivé au temps 8 — un run donne 30 % de plus, le suivant 80 %."""
        prompt, _ = self.to_prompt()
        return {
            "prompt":         prompt,
            "image_url":      image_url,       # débloque le 1080p
            "end_image_url":  end_image_url,   # verrouille l'arrivée sur le temps 8
            "resolution":     "1080p",         # 720p passerait SOUS le panneau
            "aspect_ratio":   "4:3",
            "duration":       self.api_duration,
            "generate_audio": False,           # le son, c'est le set
        }
