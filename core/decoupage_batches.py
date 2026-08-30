"""core/decoupage_batches.py — Trancher un scénario, recoller un découpage.

Le découpage d'une traite plafonne (voir `core.decoupage_scale`). Au-delà,
la seule issue est de traiter le scénario **tranche par tranche**, puis de
recoller les documents partiels en un « DÉCOUPAGE PANDORA 2 » unique et valide.

Trois opérations, toutes déterministes et sans réseau :

  `slice_screenplay`  découper le scénario aux bons endroits ;
  `carry_over`        fabriquer le rappel de continuité du lot suivant ;
  `join_batches`      recoller les documents partiels.

**Pourquoi `carry_over` existe.** La boucle anti-troncature actuelle
(`core.ai_provider.chat_until_complete_ex`) renvoie à chaque tour TOUT le texte
déjà produit : au vingtième tour on repaie en entrée les dix-neuf précédents.
Ici on refuse ce marché. Le rappel est construit depuis le document déjà
produit, de taille **bornée** : quelques centaines de jetons, que le scénario
fasse dix pages ou mille.

Module PUR : ni Qt, ni réseau, ni `core.context`. C'est ce qui le rend
testable hors ligne, donc réellement testé.
"""

from __future__ import annotations

import re
import unicodedata

from core import decoupage_scale as _scale
from core.decoupage_document import parse_v2_document, VERSION_MARKER

# ── Taille d'une tranche ─────────────────────────────────────────────────────
# Dérivée, jamais écrite en dur : une tranche doit tenir en UN SEUL tour, pour
# qu'aucun lot ne déclenche de continuation — c'est tout l'intérêt de la file.
# Marge de 35 % : les constantes de `decoupage_scale` sont des moyennes, et une
# séquence dense produit plus de document que la moyenne.
_ONE_ROUND_CHARS = (_scale.MAX_TOKENS_PER_ROUND * _scale.CHARS_PER_TOKEN
                    / _scale.EXPANSION)
SLICE_CHARS = int(_ONE_ROUND_CHARS * 0.65)      # ≈ 5 400 caractères

#: Bornes du rappel de continuité — c'est ce qui garantit sa taille constante.
CARRY_TAIL_PLANS = 3      # plans repris en fin de lot précédent
CARRY_SOURCE_CHARS = 300  # extrait du dernier plan, pour situer la reprise
CARRY_MAX_NAMES = 40      # noms rappelés au maximum, par famille

# ── Motifs de coupe, du plus fort au plus faible ─────────────────────────────
# Chacun doit matcher en DÉBUT DE LIGNE : un « INT. » au milieu d'une phrase
# n'est pas un changement de scène.
_SEQ_RE = re.compile(r"^\s*(?:—+\s*)?S[ÉE]QUENCE\s+\d+\b", re.I | re.M)
_SCENE_RE = re.compile(r"^\s*(?:INT\.|EXT\.|INT/EXT\.|INT\.?/EXT\.)", re.I | re.M)
_CHAPTER_RE = re.compile(
    r"^\s*(?:CHAPITRE|CHAPTER|PARTIE|PART|LIVRE|BOOK)\s+[\dIVXLC]+\b"
    r"|^\s*#{1,3}\s+\S"
    r"|^\s*[IVXLC]{1,7}\s*$"
    r"|^\s*\d{1,3}\s*$",
    re.I | re.M)
_PARA_RE = re.compile(r"\n\s*\n")
_SENT_RE = re.compile(r"(?<=[.!?…])\s+")

#: Ordre d'essai. Un scénario PANDORA a des SÉQUENCE ; un livre collé n'a que
#: des chapitres ou des paragraphes.
_LEVELS = (_SEQ_RE, _SCENE_RE, _CHAPTER_RE, _PARA_RE, _SENT_RE)


def _split_on(text: str, rx: re.Pattern) -> list[str]:
    """Coupe AVANT chaque occurrence, en gardant l'en-tête avec son bloc."""
    starts = [m.start() for m in rx.finditer(text)]
    starts = [s for s in starts if s > 0]
    if not starts:
        return [text]
    out, prev = [], 0
    for s in starts:
        out.append(text[prev:s])
        prev = s
    out.append(text[prev:])
    return [b for b in out if b.strip()]


def _blocks(text: str, budget: int, level: int = 0) -> list[str]:
    """Blocs insécables, aucun ne dépassant le budget si l'on peut l'éviter.

    Récursif ET par bloc : un chapitre trop gros redescend d'un niveau tout
    seul. Un découpage global au même niveau pour tout le texte laisserait
    passer le bloc géant au milieu d'un texte par ailleurs bien structuré.
    """
    text = text or ""
    if len(text) <= budget or level >= len(_LEVELS):
        return [text] if text.strip() else []
    parts = _split_on(text, _LEVELS[level])
    if len(parts) <= 1:
        return _blocks(text, budget, level + 1)
    out: list[str] = []
    for p in parts:
        out.extend(_blocks(p, budget, level + 1) if len(p) > budget else
                   ([p] if p.strip() else []))
    return out


def slice_screenplay(text: str, budget: int = SLICE_CHARS) -> list[str]:
    """Tranches de scénario, chacune traitable en un seul appel.

    Une tranche vide n'est jamais rendue ; un scénario plus court que le budget
    rend UNE tranche (et non zéro) — l'appelant n'a donc pas de cas particulier
    à écrire pour les petits scénarios.
    """
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= budget:
        return [text]

    out, cur = [], ""
    for b in _blocks(text, budget):
        if cur and len(cur) + len(b) > budget:
            out.append(cur.strip())
            cur = b
        else:
            cur += b
    if cur.strip():
        out.append(cur.strip())
    return out or [text]


# ── Rappel de continuité ─────────────────────────────────────────────────────

def _names(segments: list[dict]) -> dict[str, list[str]]:
    """Noms propres déjà employés, par famille — bornés."""
    fams = {
        "Personnages": "character_names",
        "Décors":      "decor_name",
        "Accessoires": "accessory_names",
        "Véhicules":   "vehicle_names",
    }
    out: dict[str, list[str]] = {}
    for label, key in fams.items():
        seen: list[str] = []
        for s in segments:
            v = s.get(key) or ""
            vals = v if isinstance(v, list) else [x.strip() for x in
                                                  re.split(r"[,;/]", str(v))]
            for x in vals:
                x = (x or "").strip()
                if x and x.lower() not in {y.lower() for y in seen}:
                    seen.append(x)
        if seen:
            # Borné : sans cela le rappel enflerait lot après lot et l'on
            # aurait recréé le coût quadratique qu'on cherche à fuir.
            out[label] = sorted(seen)[:CARRY_MAX_NAMES]
    return out


def carry_over(document: str, tail: int = CARRY_TAIL_PLANS) -> str:
    """Rappel à joindre au lot suivant. Taille bornée, coût constant.

    Renvoie une chaîne vide quand il n'y a rien à rappeler (premier lot) :
    l'appelant peut la concaténer sans test.
    """
    segments = parse_v2_document(document or "")
    if not segments:
        return ""

    last = segments[-tail:] if tail > 0 else []
    lignes = ["[CONTINUITÉ — FIN DU LOT PRÉCÉDENT]"]
    for s in last:
        num = s.get("number")
        bits = [f"PLAN {num}" if num else "PLAN"]
        for k in ("intention", "decor_name", "character_names"):
            v = s.get(k)
            if v:
                bits.append(str(v if not isinstance(v, list) else ", ".join(v)))
        lignes.append("  · " + " — ".join(b for b in bits if b))
    src = (last[-1].get("source") or "") if last else ""
    if src:
        lignes.append("  · dernière action traitée : « …"
                      + str(src)[-CARRY_SOURCE_CHARS:].strip() + " »")

    noms = _names(segments)
    if noms:
        lignes.append("")
        lignes.append("[NOMS DÉJÀ EMPLOYÉS — respecter la graphie exacte]")
        for label, vals in noms.items():
            lignes.append(f"  {label} : " + ", ".join(vals))

    seq = next((s.get("seq_name") for s in reversed(segments)
                if s.get("seq_name")), "")
    lignes.append("")
    lignes.append(
        "[REPRISE] Poursuis le découpage à partir de la suite du scénario "
        "ci-dessous. Numérote tes plans à partir de PLAN 01 : PANDORA "
        "renumérote l'ensemble au recollage."
        + (f" La séquence en cours est « {seq} »." if seq else ""))
    return "\n".join(lignes)


# ── Recollage ────────────────────────────────────────────────────────────────

_LABEL_RE = re.compile(
    r"^(PLAN\s+\d+|S[ÉE]QUENCE\s+\d+|[A-ZÉÈÀÂÎÔÛÇ][A-ZÉÈÀÂÎÔÛÇ \-']{2,30}\s*:)",
    re.M)


def strip_marker(lot: str) -> str:
    """Retire l'en-tête « DÉCOUPAGE PANDORA 2 » d'un lot.

    Le modèle le réécrit en tête de CHAQUE lot ; laissé en place, il se
    retrouverait au milieu du document recollé.
    """
    out = []
    for line in (lot or "").splitlines():
        if VERSION_MARKER in line.upper() and len(line.strip()) < 60:
            continue
        out.append(line)
    return "\n".join(out).strip()


def trim_trailing_prose(lot: str) -> str:
    """Coupe le bavardage final (« Dis-moi si je continue »).

    Nécessaire, et pas par élégance : la lecture d'un champ s'étend jusqu'au
    label suivant OU jusqu'à la fin du bloc. Une phrase laissée en queue est
    donc **avalée dans le dernier champ** du dernier plan, sans que la
    validation n'y voie rien.
    """
    lot = (lot or "").rstrip()
    if not lot:
        return ""
    marks = list(_LABEL_RE.finditer(lot))
    if not marks:
        return lot
    last = marks[-1]
    # On garde la ligne du dernier label ET sa valeur, mais on coupe à la
    # première ligne vide qui suit — au-delà, c'est de la prose.
    tail_start = lot.find("\n\n", last.end())
    return lot if tail_start < 0 else lot[:tail_start].rstrip()


def _norm_title(s: str) -> str:
    """Titre comparable : sans accents, sans casse, sans « (suite) »."""
    s = (s or "").strip().lower()
    s = re.sub(r"\((?:suite|cont(?:inued)?)\)|—\s*suite\b", "", s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


_SEQ_LINE_RE = re.compile(
    r"^\s*S[ÉE]QUENCE\s+\d+\s*[—–:\-]?\s*(.*?)\s*$", re.I | re.M)
_PLAN_LINE_RE = re.compile(r"^\s*PLAN\s+0*\d+\s*$", re.I | re.M)


def renumber(document: str) -> str:
    """Renumérote PLANs et SÉQUENCEs dans l'ordre du document.

    Fusionne deux en-têtes de séquence consécutifs de même titre — le modèle
    rouvre naturellement « LA ROUTE » au début du lot suivant. La comparaison
    passe par `_norm_title` : « LA ROUTE », « La route » et « LA ROUTE (suite) »
    comptent pour la même séquence.
    """
    lines = (document or "").splitlines()
    out: list[str] = []
    n_plan = 0
    n_seq = 0
    last_seq = None
    for line in lines:
        m_seq = _SEQ_LINE_RE.match(line)
        if m_seq:
            titre = m_seq.group(1).strip()
            if last_seq is not None and _norm_title(titre) == last_seq:
                continue                      # doublon de reprise : on l'absorbe
            n_seq += 1
            last_seq = _norm_title(titre)
            out.append(f"SÉQUENCE {n_seq} — {titre}" if titre
                       else f"SÉQUENCE {n_seq}")
            continue
        if _PLAN_LINE_RE.match(line):
            n_plan += 1
            out.append(f"PLAN {n_plan:02d}")
            continue
        out.append(line)
    return "\n".join(out)


def join_batches(lots: list[str]) -> str:
    """Recolle des documents partiels en un « DÉCOUPAGE PANDORA 2 » unique."""
    nettoyes = []
    for lot in (lots or []):
        t = trim_trailing_prose(strip_marker(lot))
        if t.strip():
            nettoyes.append(t.strip())
    if not nettoyes:
        return ""
    return renumber(VERSION_MARKER + "\n\n" + "\n\n".join(nettoyes)).strip()


def plan_count(document: str) -> int:
    """Nombre de plans réellement RELUS — pas le nombre écrit.

    L'écart entre les deux est ce qui a fait disparaître des plans en silence
    jusqu'ici ; l'appelant doit pouvoir le vérifier.
    """
    return len(parse_v2_document(document or ""))
