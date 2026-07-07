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


def has_header(text: str) -> bool:
    """Vrai si ``text`` commence par un en-tête de plan reconnaissable
    (« P0N | … » Cinéma ou « PLAN n — … » Live). Sert à garantir qu'un plan réécrit
    par l'IA garde son en-tête — sinon ``split_plans`` le fusionnerait au plan
    précédent et un plan disparaîtrait."""
    return bool(_PLAN_RE.match((text or "").lstrip()))


# ── Réordonner / ajouter / supprimer des plans ───────────────────────────────
# Le NUMÉRO d'en-tête est renuméroté séquentiellement après chaque opération, dans
# le format détecté : « P01 | … » (Cinéma) ou « PLAN 1 — … » (Live).

def _head_and_blocks(layout_text: str):
    """(head, [blocs]) : head = tout ce qui précède le 1er plan (titres/séquences),
    chaque bloc = le texte d'un plan (jusqu'au plan suivant)."""
    plans = split_plans(layout_text)
    if not plans:
        return layout_text, []
    head = layout_text[:plans[0]["start"]]
    return head, [p["text"] for p in plans]


def _renumber_block(block: str, n: int) -> str:
    """Renumérote l'en-tête d'un bloc plan : « P0X | » → « P{n:02d} | » (Cinéma) ou
    « PLAN X » → « PLAN n » (Live). Bloc non reconnu : renvoyé inchangé."""
    if re.match(r"^\s*P\d{1,3}\s*\|", block):
        return re.sub(r"^(\s*)P\d{1,3}(\s*\|)", rf"\g<1>P{n:02d}\g<2>", block, count=1)
    if re.match(r"^\s*PLAN\s+\d{1,3}\b", block):
        return re.sub(r"^(\s*)PLAN\s+\d{1,3}\b", rf"\g<1>PLAN {n}", block, count=1)
    return block


def _rebuild(head: str, blocks: list) -> str:
    """Recompose la mise en page (head + plans renumérotés séparés par une ligne vide)."""
    numbered = [_renumber_block(b.strip(), i) for i, b in enumerate(blocks, 1) if b.strip()]
    body = "\n\n".join(numbered)
    head = head.rstrip()
    if head and body:
        return head + "\n\n" + body + "\n"
    return (head or body) + ("\n" if body else "")


def _blank_plan(edition: str) -> str:
    """Gabarit de plan VIERGE (le numéro sera réattribué par la renumérotation)."""
    if edition == "cinema":
        return ("P01 | Plan moyen | Fixe | Face | ~5s\n"
                "INT./EXT. LIEU PRÉCIS — MOMENT\n"
                "Description de l'action, au présent, concrète et visuelle.\n"
                "→ SEEDANCE: à décrire…")
    return ("PLAN 1 — Nouveau plan\n"
            "Durée : 5s · Valeur de plan : … · Mouvement : …\n"
            "PROMPT VIDÉO (français) : « à décrire… »\n"
            "PROMPT SON (sound design / SFX, français) : « à décrire… »")


def move_plan(layout_text: str, index: int, delta: int) -> str:
    """Déplace le plan ``index`` de ``delta`` positions (−1 = monter, +1 = descendre).
    Renumérote. Renvoie le texte inchangé si le mouvement sort des bornes."""
    head, blocks = _head_and_blocks(layout_text)
    j = index + delta
    if not blocks or not (0 <= index < len(blocks)) or not (0 <= j < len(blocks)):
        return layout_text
    blocks[index], blocks[j] = blocks[j], blocks[index]
    return _rebuild(head, blocks)


def delete_plan(layout_text: str, index: int) -> str:
    """Supprime le plan ``index`` et renumérote le reste."""
    head, blocks = _head_and_blocks(layout_text)
    if not blocks or not (0 <= index < len(blocks)):
        return layout_text
    blocks.pop(index)
    return _rebuild(head, blocks)


def add_plan(layout_text: str, index: int, edition: str = "live") -> str:
    """Insère un plan VIERGE juste APRÈS ``index`` (ou en tête si index < 0 / aucun
    plan). Renumérote. ``edition`` : « cinema » ou « live »."""
    head, blocks = _head_and_blocks(layout_text)
    pos = 0 if (index < 0 or not blocks) else min(len(blocks), index + 1)
    blocks.insert(pos, _blank_plan("cinema" if edition == "cinema" else "live"))
    return _rebuild(head, blocks)


def duplicate_plan(layout_text: str, index: int) -> str:
    """Duplique le plan ``index`` (copie insérée juste après) et renumérote."""
    head, blocks = _head_and_blocks(layout_text)
    if not blocks or not (0 <= index < len(blocks)):
        return layout_text
    blocks.insert(index + 1, blocks[index])
    return _rebuild(head, blocks)


def reorder(layout_text: str, new_order: list) -> str:
    """Réordonne les plans selon ``new_order`` (liste des index d'ORIGINE dans le
    nouvel ordre) et renumérote. Ordre invalide → texte inchangé."""
    head, blocks = _head_and_blocks(layout_text)
    try:
        order = [int(k) for k in new_order]
    except (TypeError, ValueError):
        return layout_text
    if sorted(order) != list(range(len(blocks))):
        return layout_text
    return _rebuild(head, [blocks[k] for k in order])


def renumber_all(layout_text: str) -> str:
    """Renumérote séquentiellement TOUS les plans (P01..P0N / PLAN 1..n) sans changer
    leur ordre ni leur contenu (le head — titres/séquences — est préservé)."""
    head, blocks = _head_and_blocks(layout_text)
    if not blocks:
        return layout_text
    return _rebuild(head, blocks)


def replace_plan_multi(layout_text: str, plan_index: int, multi_text: str) -> str:
    """Remplace le plan ``plan_index`` par UN OU PLUSIEURS blocs de plan (``multi_text``
    peut contenir plusieurs en-têtes), PUIS renumérote TOUTE la mise en page pour
    décaler les plans suivants (27 → 28…). Sert à la co-écriture quand le chat crée un
    nouveau plan. Texte vide / index hors bornes : comportement de ``replace_plan``."""
    if not multi_text or not multi_text.strip():
        return layout_text
    spliced = replace_plan(layout_text, plan_index, multi_text)
    return renumber_all(spliced)
