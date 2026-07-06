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


def apply_find_replace_edits(text: str, edits: list[dict]):
    """Applique les édits ``{find, replace}`` au texte (1re occurrence de chaque `find`).

    Tolérant aux espaces : si le `find` exact est introuvable, on retente en
    autorisant n'importe quelle suite d'espaces entre les mots (le modèle
    reproduit parfois les blancs différemment). Retourne
    ``(nouveau_texte, appliqués, non_localisés)``.
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
        # Repli tolérant aux espaces : mots du `find` reliés par \s+.
        toks = find.split()
        if not toks:
            missed.append(e)
            continue
        pat = r"\s+".join(re.escape(t) for t in toks)
        m = re.search(pat, text)
        if m:
            text = text[:m.start()] + repl + text[m.end():]
            applied.append(e)
        else:
            missed.append(e)
    return text, applied, missed
