"""core/ai_spend.py — Ce que coûtent réellement les appels IA de TEXTE.

Le poste le plus cher du logiciel était le seul qui n'était pas compté :
`core.spend.KIND_TEXT` existait, la fenêtre « Coût du projet » affichait bien
la ligne « Texte (IA) », mais personne ne l'écrivait. Un utilisateur l'a
signalé — son analyse et son découpage n'apparaissaient nulle part.

Or l'information était là : le SDK Anthropic renvoie `msg.usage`
(`input_tokens` / `output_tokens`) à chaque réponse, et le code le jetait.
Ce module la ramasse et la convertit en dollars.

Trois principes, tenus par le code plus bas :

  - **Ne jamais faire échouer un appel déjà payé.** Toute la fonction est sous
    `try/except`. Un journal qui rate est un journal qui rate, pas une
    génération perdue.
  - **Ne jamais écrire hors d'un projet.** `core.spend` écrit dans le projet
    courant ; sans projet ouvert, il retomberait dans le dossier de
    l'application. On s'abstient plutôt que de polluer.
  - **Zéro ne veut pas dire gratuit.** Un modèle absent de la grille est
    journalisé à 0 $ avec la mention explicite « tarif inconnu » : l'interface
    doit pouvoir le dire, jamais laisser croire à la gratuité.
"""

from __future__ import annotations

#: Grille Anthropic en $ par MILLION de jetons — (entrée, sortie).
#: ⚠ Tarifs annoncés au 2026-08-30, NON confrontés à une facture réelle.
#: Une clé absente = tarif inconnu, pas gratuit (voir `price_for`).
ANTHROPIC_PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-5":        (15.0, 75.0),
    "claude-opus-4-8":      (15.0, 75.0),
    "claude-sonnet-5":      (3.0, 15.0),
    "claude-haiku-4-5":     (1.0, 5.0),
}

#: Repli par famille : un identifiant versionné inconnu (« claude-sonnet-5-2026… »)
#: doit tout de même être tarifé, sinon toute la ligne texte tombe à zéro.
_FAMILIES: tuple[tuple[str, tuple[float, float]], ...] = (
    ("opus",   (15.0, 75.0)),
    ("sonnet", (3.0, 15.0)),
    ("haiku",  (1.0, 5.0)),
)


def price_for(model: str) -> tuple[float, float] | None:
    """(prix entrée, prix sortie) par million de jetons, ou None si inconnu."""
    m = (model or "").strip().lower()
    if not m:
        return None
    if m in ANTHROPIC_PRICES:
        return ANTHROPIC_PRICES[m]
    for needle, prices in _FAMILIES:
        if needle in m:
            return prices
    return None


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    p = price_for(model)
    if not p:
        return 0.0
    return round(input_tokens / 1e6 * p[0] + output_tokens / 1e6 * p[1], 6)


def _project_is_open() -> bool:
    """Vrai si un projet est ouvert ET porte un chemin exploitable.

    On teste `get_project_path()` et non `get_data_root()` : le second retombe
    silencieusement sur le dossier `data/` de l'application, ce qui écrirait le
    journal d'un film dans l'installation. Ce piège a déjà coûté un fichier
    parasite dans ce projet.
    """
    try:
        from core.context import get_project_path
        return bool((get_project_path() or "").strip())
    except Exception:
        return False


def note_usage(model: str, task: str, input_tokens: int, output_tokens: int,
               provider: str = "anthropic", label: str = "") -> float:
    """Journalise un appel IA texte. Renvoie le coût estimé (0.0 si inconnu).

    Ne lève jamais.
    """
    try:
        it = max(0, int(input_tokens or 0))
        ot = max(0, int(output_tokens or 0))
        if not (it or ot):
            return 0.0
        cost = cost_usd(model, it, ot) if provider == "anthropic" else 0.0

        if not _project_is_open():
            return cost

        from core import spend
        known = price_for(model) is not None and provider == "anthropic"
        detail = f"{it:,} → {ot:,} jetons".replace(",", " ")
        if not known:
            detail += "  ·  tarif inconnu"
        spend.record(
            spend.KIND_TEXT,
            (model or provider or "IA texte"),
            (label or task or "appel IA"),
            cost_usd=cost,
            detail=detail,
            estimated=True,
        )
        return cost
    except Exception:
        # Un journal indisponible ne doit pas remonter dans l'appel IA.
        return 0.0


def note_message(msg, model: str, task: str, provider: str = "anthropic",
                 label: str = "") -> float:
    """Variante qui lit `msg.usage` d'une réponse Anthropic.

    Tolère un objet sans `usage` (autre fournisseur, réponse simulée) : dans ce
    cas rien n'est journalisé et 0.0 est rendu.
    """
    try:
        usage = getattr(msg, "usage", None)
        if usage is None:
            return 0.0
        return note_usage(model, task,
                          getattr(usage, "input_tokens", 0) or 0,
                          getattr(usage, "output_tokens", 0) or 0,
                          provider=provider, label=label)
    except Exception:
        return 0.0
