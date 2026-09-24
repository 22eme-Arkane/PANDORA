"""core/markers.py — Marqueurs de blocs tolérants aux approximations des modèles.

Les réponses en blocs de PANDORA sont découpées sur des lignes du type
« ══════════ MESSAGE ══════════ » (coécriture du scénario, du conducteur
Live, des plans). Claude les reproduit au caractère près ; un modèle local
en perd parfois un « ═ » (qwen2.5vl : 9 au lieu de 10, constaté par
tools/ai_conformance le 24/09/2026), les remplace par « = » ou « ─ », ou
change l'espacement — et le découpage exact ne trouvait plus le marqueur :
tout le bloc devenait « message », le document réécrit était PERDU en
silence.

`normalize_markers` ramène toute variante raisonnable au marqueur canonique
AVANT le découpage. Le mot-clé, lui, doit être exact (casse comprise) : c'est
lui qui porte le sens. Module PUR.
"""

from __future__ import annotations

import re

_RUN = r"[═=─—]{3,}"


def _word_of(marker: str) -> str:
    return marker.strip("═=─— \t").strip()


def normalize_markers(text: str, markers) -> str:
    """Réécrit chaque variante d'un marqueur (traits ═/=/─ de longueur ≥ 3,
    espaces libres) sous sa forme canonique. Texte sans marqueur → inchangé."""
    if not text:
        return text or ""
    out = text
    for canon in markers:
        word = _word_of(canon)
        if not word:
            continue
        pat = re.compile(_RUN + r"[ \t]*" + re.escape(word) + r"[ \t]*" + _RUN)
        out = pat.sub(canon, out)
    return out


def has_marker(text: str, marker: str) -> bool:
    return marker in normalize_markers(text or "", (marker,))
