"""core/storyboard_batches.py — Trancher un découpage, recoller des plans.

Pendant du `core.decoupage_batches`, mais un cran plus loin dans la chaîne :
ici l'entrée est un document « DÉCOUPAGE PANDORA 2 » déjà écrit, et la sortie
une liste de plans de storyboard.

Le problème est le même : `GenerateStoryboardWorker` demande à l'IA de
convertir TOUTES les fiches en un seul appel, plafonné à 16 000 jetons. Sur un
découpage de plusieurs centaines de fiches, la réponse se coupe — et un
découpage amputé passe le contrat, puisque chaque plan qu'il contient est bien
formé. On tranche donc le document en sous-documents valides, chacun traitable
en un appel.

Deux règles qui font toute la difficulté :

  - **Chaque sous-document doit rester un vrai document v2**, en-tête compris,
    sinon le parseur et le repli déterministe le rejettent.
  - **La séquence en cours doit voyager.** Un plan hérite de la DERNIÈRE ligne
    `SÉQUENCE` qui le précède ; couper juste après un en-tête laisserait la
    tranche suivante sans séquence, et `seq_num`/`seq_name` — qui alimentent la
    détection de récurrence — repartiraient à vide.

Module PUR : ni Qt, ni réseau.
"""

from __future__ import annotations

import re

from core.decoupage_document import VERSION_MARKER

#: Fiches par lot. Une fiche produit un enregistrement JSON de l'ordre de 700 à
#: 800 jetons ; à 16 000 jetons de plafond, la coupure arrive vers la vingtième.
#: On reste nettement en dessous pour qu'aucun lot n'ait besoin de continuation
#: — c'est tout l'intérêt de la file.
FICHES_PER_BATCH = 12

_PLAN_LINE = re.compile(r"^PLAN\s+0*\d+\s*$", re.I | re.M)
_SEQ_LINE = re.compile(r"^\s*S[ÉE]QUENCE\s+\d+\s*[—–:\-]?\s*.*$", re.I | re.M)


def _blocks(document: str) -> list[tuple[str, str]]:
    """Découpe le document en (séquence courante, bloc de fiche).

    La séquence courante est mémorisée au fil de la lecture : c'est elle qui
    sera réinjectée en tête de chaque sous-document.
    """
    text = document or ""
    starts = [m.start() for m in _PLAN_LINE.finditer(text)]
    if not starts:
        return []
    out: list[tuple[str, str]] = []
    for i, s in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        bloc = text[s:end].rstrip()
        # Dernier en-tête de séquence rencontré AVANT cette fiche.
        seq = ""
        for m in _SEQ_LINE.finditer(text, 0, s):
            seq = m.group(0).strip()
        # Une ligne SÉQUENCE peut aussi se trouver DANS le bloc (elle ouvre la
        # séquence de la fiche suivante) : on la laisse où elle est.
        out.append((seq, bloc))
    return out


def split_document(document: str,
                   per_batch: int = FICHES_PER_BATCH) -> list[str]:
    """Sous-documents v2, `per_batch` fiches chacun au plus.

    Un document sans fiche rend une liste vide ; un document qui tient déjà
    dans un lot en rend UN — l'appelant n'a pas de cas particulier à écrire.
    """
    blocs = _blocks(document)
    if not blocs:
        return []
    per = max(1, int(per_batch or FICHES_PER_BATCH))

    lots: list[str] = []
    for i in range(0, len(blocs), per):
        tranche = blocs[i:i + per]
        seq_ouverte = tranche[0][0]
        corps = "\n\n".join(b for _, b in tranche)
        tete = VERSION_MARKER + "\n\n"
        # On réinjecte la séquence en cours SEULEMENT si la tranche ne l'ouvre
        # pas déjà elle-même : sinon on la déclarerait deux fois.
        if seq_ouverte and not corps.lstrip().upper().startswith("SÉQUENCE"):
            tete += seq_ouverte + "\n\n"
        lots.append(tete + corps)
    return lots


def count_fiches(document: str) -> int:
    """Nombre de fiches PLAN du document."""
    return len(_PLAN_LINE.findall(document or ""))


def batches_needed(document: str, per_batch: int = FICHES_PER_BATCH) -> int:
    n = count_fiches(document)
    per = max(1, int(per_batch or FICHES_PER_BATCH))
    return (n + per - 1) // per if n else 0


def merge_shots(groupes: list[list[dict]]) -> list[dict]:
    """Recolle les plans de plusieurs lots en une liste continue.

    Chaque lot repart de `number = 1` — la conversion déterministe renumérote
    par `enumerate`, et l'IA fait de même. Sans renumérotation globale, le
    storyboard contiendrait douze « plan 1 ».

    Les dicts sont COPIÉS : les listes d'origine appartiennent aux workers de
    lot, qui peuvent être détruits.
    """
    out: list[dict] = []
    n = 0
    for groupe in (groupes or []):
        for shot in (groupe or []):
            if not isinstance(shot, dict):
                continue
            s = dict(shot)
            n += 1
            s["number"] = n
            out.append(s)
    return out
