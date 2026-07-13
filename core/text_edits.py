"""Éditions chirurgicales {find, replace} sur un texte libre.

Utilisé par l'enrichissement « Références visuelles » (conducteur / scénario) :
au lieu de réécrire tout le document, le modèle ne renvoie QUE les passages
modifiés — `find` = extrait EXACT du texte d'origine, `replace` = version
enrichie. Moins de tokens en sortie, et tout le reste du texte reste MOT POUR MOT.

Aucune dépendance UI — testable hors ligne.
"""
import json
import re

_WS = re.compile(r"\s+")


def parse_edits(raw: str) -> list[dict]:
    """Extrait la liste d'édits ``{find, replace, summary?}`` d'une sortie modèle.

    Tolère un JSON entouré de markdown (```json … ```), un objet ``{"edits": [...]}``
    ou une liste nue ``[...]``. Retourne ``[]`` si rien d'exploitable.
    """
    if not raw:
        return []
    s = raw.strip()
    if "```" in s:                       # ```json … ```
        for part in s.split("```"):
            cand = part.lstrip("json").strip()
            if cand.startswith("{") or cand.startswith("["):
                s = cand
                break
    data = None
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"[\{\[].*[\}\]]", s, re.DOTALL)   # isole le 1er bloc JSON
        if m:
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                data = None
    if isinstance(data, dict):
        data = data.get("edits", [])
    if not isinstance(data, list):
        return []
    out = []
    for e in data:
        if (isinstance(e, dict)
                and isinstance(e.get("find"), str) and e["find"].strip()
                and isinstance(e.get("replace"), str)):
            out.append({"find": e["find"], "replace": e["replace"],
                        "summary": str(e.get("summary", "")).strip()})
    return out


# Caractères typographiques équivalents : le scénario est saisi avec les signes
# français (' « » – …) mais le modèle renvoie souvent leurs variantes droites
# (' " - ...) — cause RÉELLE de « passage non retrouvé » (constat 2026-07-13).
_EQUIV = {
    "'": "['’‘‛`]", "’": "['’‘‛`]", "‘": "['’‘‛`]", "‛": "['’‘‛`]",
    "-": "[-–—]", "–": "[-–—]", "—": "[-–—]",
    "…": r"(?:…|\.\.\.)",
}
_DQUOTES = '"“”«»„'   # guillemets doubles — « » s'écrivent AVEC espaces intérieures


def _tolerant_pattern(find: str) -> str:
    """Regex du `find` tolérante aux espaces (y c. insécables) ET aux variantes
    typographiques (apostrophes, guillemets, tirets, points de suspension).
    Les espaces voisines d'un guillemet deviennent OPTIONNELLES : « Adieu » ↔ "Adieu"
    doivent se retrouver dans les deux sens."""
    units, i, n = [], 0, len(find)
    while i < n:
        ch = find[i]
        if ch.isspace():
            while i < n and find[i].isspace():
                i += 1
            units.append((r"\s+", "ws"))
            continue
        if find.startswith("...", i):             # ... écrit par le modèle ↔ … du texte
            units.append((r"(?:…|\.\.\.)", "ch"))
            i += 3
            continue
        if ch in _DQUOTES:
            units.append((r'(?:\s*["“”«»„]\s*)', "q"))
            i += 1
            continue
        units.append((_EQUIV.get(ch) or re.escape(ch), "ch"))
        i += 1
    out = []
    for k, (pat, typ) in enumerate(units):
        if typ == "ws":
            near_q = ((k > 0 and units[k - 1][1] == "q")
                      or (k + 1 < len(units) and units[k + 1][1] == "q"))
            out.append(r"\s*" if near_q else r"\s+")
        else:
            out.append(pat)
    return "".join(out)


def apply_find_replace_edits(text: str, edits: list[dict]):
    """Applique les édits ``{find, replace}`` au texte (1re occurrence de chaque `find`).

    Deux niveaux : correspondance exacte, puis repli TOLÉRANT — n'importe quelle
    suite d'espaces entre les mots ET variantes typographiques équivalentes
    (' ↔ ', « » ↔ ", – ↔ -, … ↔ ...) : le modèle reproduit rarement ces signes
    à l'identique. Retourne ``(nouveau_texte, appliqués, non_localisés)``.
    """
    applied, missed = [], []
    for e in edits:
        find = e.get("find", "")
        repl = e.get("replace", "")
        if not find:
            continue
        idx = text.find(find)
        if idx >= 0:
            text = text[:idx] + repl + text[idx + len(find):]
            applied.append(e)
            continue
        # Repli tolérant (espaces + typographie).
        toks = find.split()
        if not toks:
            missed.append(e)
            continue
        m = re.search(_tolerant_pattern(find), text)
        if m:
            text = text[:m.start()] + repl + text[m.end():]
            applied.append(e)
        else:
            missed.append(e)
    return text, applied, missed
