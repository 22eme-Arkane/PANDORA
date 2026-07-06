"""Découpage d'une « Mise en page PANDORA » en plans individuels.

La mise en page générée (Cinéma via FormatPandoraWorker, Live via
FormatConducteurWorker) est un TEXTE. Cet outil la parse en plans pour la
co-écriture plan par plan, puis réinjecte UN plan réécrit à sa place
(édition chirurgicale — les autres plans restent intacts).

Deux formats gérés, avec la MÊME regex d'en-tête :
  - Cinéma : « P01 | Valeur | Mouvement | Axe | ~Durée »
  - Live   : « PLAN 1 — Titre court »

Aucune dépendance UI — testable hors ligne.
"""
import re

# Début d'un plan : « P01 | … » (Cinéma) ou « PLAN 1 — … » (Live/Conducteur).
# « P\d » n'attrape jamais « PLAN » (lettre L après P, pas un chiffre).
_PLAN_RE = re.compile(r"^(P\d{1,3}\s*\||PLAN\s+\d{1,3}\b)", re.MULTILINE)


def split_plans(layout_text: str) -> list[dict]:
    """Découpe la mise en page en plans.

    Retourne une liste de dicts ``{index, label, text, start, end}`` où
    ``start``/``end`` sont des offsets caractères dans ``layout_text``
    (pour un remplacement chirurgical). Tout ce qui précède le 1er plan
    (titres de séquence/acte) reste attaché — via les offsets — au reste du
    document, jamais perdu.
    """
    if not layout_text:
        return []
    starts = [m.start() for m in _PLAN_RE.finditer(layout_text)]
    if not starts:
        return []
    plans: list[dict] = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(layout_text)
        block = layout_text[s:e]
        stripped = block.strip()
        first_line = stripped.splitlines()[0].strip() if stripped else ""
        plans.append({
            "index": i,
            "label": first_line[:90],
            "text":  block.rstrip(),
            "start": s,
            "end":   e,
        })
    return plans


def plan_count(layout_text: str) -> int:
    """Nombre de plans détectés dans la mise en page."""
    if not layout_text:
        return 0
    return len(_PLAN_RE.findall(layout_text))


def replace_plan(layout_text: str, plan_index: int, new_plan_text: str) -> str:
    """Remplace le plan ``plan_index`` par ``new_plan_text`` (chirurgical).

    Le reste de la mise en page (autres plans, titres de séquence/acte) est
    conservé à l'identique. Retourne le texte inchangé si l'index est hors
    bornes ou si le nouveau texte est vide.
    """
    if not new_plan_text or not new_plan_text.strip():
        return layout_text
    plans = split_plans(layout_text)
    if plan_index < 0 or plan_index >= len(plans):
        return layout_text
    p = plans[plan_index]
    before = layout_text[:p["start"]]
    after  = layout_text[p["end"]:]
    block  = new_plan_text.strip()
    # Séparation nette avant le plan suivant (les lignes vides d'origine
    # faisaient partie du bloc courant, retirées par strip()).
    tail = "" if not after.strip() else "\n\n" + after.lstrip("\n")
    return before + block + tail
