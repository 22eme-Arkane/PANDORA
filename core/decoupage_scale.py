"""core/decoupage_scale.py — Ce que va coûter un découpage, AVANT de le lancer.

Un utilisateur a collé un livre entier dans le Scénario. L'analyse est passée,
le découpage s'est arrêté — et c'était inévitable : le découpage produit
**six fois** la taille de son entrée, et la boucle anti-troncature plafonne.

Ce module répond à deux questions, et à elles seules :
  - combien de plans, de caractères et de jetons ce scénario va-t-il produire ?
  - est-ce que ça peut seulement tenir dans le pipeline actuel ?

Il ne fait aucun appel réseau et ne connaît ni Qt ni l'interface : c'est
l'unique source de vérité, partagée par l'avertissement et par la file de lots.

─────────────────────────────────────────────────────────────────────────────
D'OÙ VIENNENT LES CONSTANTES — mesuré le 2026-08-30 sur les découpages RÉELS
du disque (``PANDORA/_Projets/*/data/scenarios/index.json``), pas estimé :

    projet          scénario   document   plans   expansion   scén./plan
    FIGHTER           15 256     94 053      84      ×6,2         182
    FIGHTER V2        15 256     94 053      84      ×6,2         182

« Mapping Forcalquier » (10 760 → 22 656, ×2,1) est ÉCARTÉ du calibrage : un
projet de mapping n'a ni dialogues ni découpage cinéma, son régime est autre.
Deux films seulement : c'est peu, et les chiffres ci-dessous sont donc un ordre
de grandeur, pas une garantie. ``MEASURED_ON`` le dit à l'appelant.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

#: Caractères de scénario consommés par plan produit (mesuré : 182).
SCREENPLAY_CHARS_PER_SHOT = 182
#: Caractères de document produits par plan (mesuré : 1 120).
DOCUMENT_CHARS_PER_SHOT = 1120
#: Expansion document / scénario (mesuré : ×6,2).
EXPANSION = DOCUMENT_CHARS_PER_SHOT / SCREENPLAY_CHARS_PER_SHOT

#: Caractères par jeton en français. HYPOTHÈSE — aucun tokenizer n'est embarqué
#: dans PANDORA. Une estimation prudente : la vraie valeur tourne autour de 3 à
#: 3,5 pour du français accentué. Sous-estimer ce nombre gonfle les jetons, donc
#: l'avertissement se déclenche plus tôt — c'est le sens sûr.
CHARS_PER_TOKEN = 3.2

#: Plafond du pipeline actuel : api/screenplay.py `_DECOUPAGE_MAX_ROUNDS = 6`
#: plus l'appel initial, à `max_tokens=16000` chacun.
MAX_TOKENS_PER_ROUND = 16000
MAX_ROUNDS = 7

MEASURED_ON = "2 découpages réels (FIGHTER, FIGHTER V2) — 2026-08-30"

#: Verdicts.
OK         = "ok"          # tient en un ou deux tours
HEAVY      = "lourd"       # tient, mais au prix de plusieurs continuations
IMPOSSIBLE = "impossible"  # ne peut pas aboutir en un seul découpage


def _round_up(a: float) -> int:
    return int(a) + (1 if a > int(a) else 0)


def estimate(text: str) -> dict:
    """Ce que ce scénario va produire. Tout est estimé, rien n'est mesuré ici.

    Renvoie un dict aux clés stables :
      chars, shots, document_chars, output_tokens, rounds_needed,
      max_rounds, verdict, fits.
    """
    chars = len(text or "")
    if chars == 0:
        return {
            "chars": 0, "shots": 0, "document_chars": 0, "output_tokens": 0,
            "rounds_needed": 0, "max_rounds": MAX_ROUNDS,
            "verdict": OK, "fits": True,
        }

    shots = max(1, _round_up(chars / SCREENPLAY_CHARS_PER_SHOT))
    doc_chars = shots * DOCUMENT_CHARS_PER_SHOT
    out_tokens = _round_up(doc_chars / CHARS_PER_TOKEN)
    rounds = max(1, _round_up(out_tokens / MAX_TOKENS_PER_ROUND))

    if rounds > MAX_ROUNDS:
        verdict = IMPOSSIBLE
    elif rounds > 2:
        verdict = HEAVY
    else:
        verdict = OK

    return {
        "chars": chars,
        "shots": shots,
        "document_chars": doc_chars,
        "output_tokens": out_tokens,
        "rounds_needed": rounds,
        "max_rounds": MAX_ROUNDS,
        "verdict": verdict,
        "fits": rounds <= MAX_ROUNDS,
    }


#: Caractères de scénario au-delà desquels le découpage NE PEUT PAS aboutir
#: d'une traite. Dérivé des constantes, jamais écrit en dur : si le plafond du
#: pipeline change, ce seuil suit.
def max_chars_single_pass() -> int:
    return int(MAX_ROUNDS * MAX_TOKENS_PER_ROUND * CHARS_PER_TOKEN / EXPANSION)


def batches_needed(text: str, budget_chars: int) -> int:
    """Nombre de lots pour traiter ce scénario par tranches de `budget_chars`."""
    chars = len(text or "")
    if chars <= 0 or budget_chars <= 0:
        return 0
    return max(1, _round_up(chars / budget_chars))


def cost_estimate_usd(text: str, price_in_per_mtok: float,
                      price_out_per_mtok: float) -> float:
    """Coût estimé d'un découpage d'une traite, **continuations comprises**.

    Le point qui rend ce calcul non trivial : la boucle anti-troncature
    (`core/ai_provider.chat_until_complete_ex`) renvoie à chaque tour TOUT le
    texte déjà produit. L'entrée croît donc en triangle — au tour N on repaie
    en entrée la sortie des tours 1..N-1. Ignorer cela sous-estime lourdement
    un gros scénario, qui est précisément le cas qu'on veut chiffrer.
    """
    e = estimate(text)
    if not e["shots"]:
        return 0.0

    prompt_tokens = _round_up(e["chars"] / CHARS_PER_TOKEN)
    per_round_out = e["output_tokens"] / max(1, e["rounds_needed"])

    tok_in = 0.0
    for r in range(e["rounds_needed"]):
        # Tour r : le prompt d'origine + tout ce qui a déjà été produit.
        tok_in += prompt_tokens + per_round_out * r
    tok_out = e["output_tokens"]

    return round(tok_in / 1e6 * price_in_per_mtok
                 + tok_out / 1e6 * price_out_per_mtok, 2)
