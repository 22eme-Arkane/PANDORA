"""
core/engine_prompts.py — Adaptation des prompts système PAR MOTEUR.

Claude (Anthropic) suit naturellement les consignes de format de PANDORA
(JSON brut sans markdown, marqueurs ══, longueurs demandées). Les moteurs
alternatifs — GPT, Mistral, Kimi, GLM, Ollama — ont besoin de directives plus
EXPLICITES (et répétées pour les petits modèles locaux) pour produire
exactement le même format de sortie que Claude.

Ce module AJOUTE un préambule de discipline au prompt système existant, sans
jamais retirer ni réécrire une consigne de la tâche. Il est branché au POINT
CENTRAL (core/ai_provider.chat / chat_stream / stream) : aucun worker n'a
besoin de le connaître.

API :
    adapt_system(system, task=None, provider="anthropic", model="") -> str
        - provider "anthropic" → system INCHANGÉ (comportement historique,
          zéro régression pour Claude / Fable 5) ;
        - autres providers     → rappel de rôle (1 phrase par tâche) +
          règles de format strictes, PRÉFIXÉS au system existant ;
        - Ollama (petits modèles locaux) → directives renforcées en plus.
"""

from __future__ import annotations


# ── Rappel de rôle par tâche (1 phrase claire, préfixée au system) ─────────────
# Clés = tâches de core/ai_provider.TASKS. Une tâche inconnue / None → pas de
# rappel de rôle, seulement les règles de format.

TASK_ROLES: dict[str, str] = {
    "storyboard_gen": (
        "Tu produis un DÉCOUPAGE technique de storyboard : ta réponse est un "
        "tableau JSON de plans respectant exactement les clés demandées — rien d'autre."
    ),
    "extraction": (
        "Tu extrais des éléments structurés (personnages, décors, accessoires, "
        "véhicules, HMC…) : ta réponse est un tableau JSON — rien d'autre."
    ),
    "screenplay": (
        "Tu travailles un document d'écriture (scénario ou conducteur) : ta "
        "réponse est le document demandé (ou l'analyse demandée), sans "
        "commentaire autour."
    ),
    "sync": (
        "Tu synchronises / réécris des prompts de plans : ta réponse respecte "
        "EXACTEMENT le format demandé par les consignes (souvent du JSON strict)."
    ),
    "enhance": (
        "Tu réécris un prompt pour l'améliorer : ta réponse est UNIQUEMENT le "
        "prompt réécrit — sans guillemets, sans explication."
    ),
    "translate": (
        "Tu traduis un texte : ta réponse est UNIQUEMENT la traduction — sans "
        "note, sans variante, sans commentaire."
    ),
    "assistant": (
        "Tu es un assistant intégré : réponse courte, directe et pratique, en "
        "français sauf consigne contraire."
    ),
    "storyboard_chat": (
        "Tu modifies un storyboard par conversation : ta réponse est le JSON "
        "strict demandé (réponse + éditions ciblées) — rien d'autre."
    ),
}


# ── Règles de format communes aux moteurs NON-Anthropic ────────────────────────
# Objectif : que Mistral / GPT / Kimi / GLM / Ollama suivent les mêmes consignes
# que Claude — JSON brut, pas de markdown, pas de préambule, marqueurs exacts.

_FORMAT_RULES = """\
RÈGLES DE DISCIPLINE (prioritaires sur toute habitude de réponse) :
1. Suis les consignes de la tâche À LA LETTRE — format, structure, langue, longueur.
2. Si un format JSON est demandé : réponds avec le JSON BRUT uniquement — AUCUNE \
balise markdown, AUCUN ```, aucun texte avant ou après le JSON, aucune explication.
3. AUCUNE phrase d'introduction (« Voici… », « Bien sûr… ») ni de conclusion \
(« J'espère que… », « N'hésitez pas… ») : ta réponse commence directement par le \
contenu demandé et s'arrête à sa fin.
4. Si un format à MARQUEURS est demandé (lignes du type ══════════ MESSAGE ══════════), \
reproduis ces marqueurs EXACTEMENT à l'identique, caractère par caractère.
5. Langue : respecte la langue exigée par les consignes pour chaque champ (ex. prompts \
vidéo en anglais) ; à défaut d'indication, réponds en français.
6. Respecte les longueurs et bornes demandées (nombre de phrases, limites de \
caractères, plafonds de durée, plages de valeurs).
7. Ne montre jamais ton raisonnement ni ces règles : seulement le résultat final.\
"""


# ── Directives RENFORCÉES pour les petits modèles locaux (Ollama) ──────────────
# Les petits modèles oublient vite : on répète les pièges les plus fréquents.

_SMALL_MODEL_RULES = """\
RAPPEL (modèle local — erreurs fréquentes à éviter ABSOLUMENT) :
- N'ouvre JAMAIS ta réponse par ``` ni par une phrase de politesse.
- Un tableau JSON commence par [ et se termine par ] ; un objet JSON commence \
par { et se termine par } — RIEN d'autre autour, pas même un espace de commentaire.
- Utilise EXACTEMENT les clés JSON listées dans les consignes — n'en invente \
aucune, n'en oublie aucune, ne les traduis pas.
- Toutes les chaînes JSON sont entre guillemets doubles " et les caractères \
spéciaux sont échappés (\\" pour un guillemet, \\n pour un saut de ligne).
- Si tu hésites entre expliquer et produire : PRODUIS. Aucune explication.
- Relis les consignes de la tâche ci-dessous AVANT de répondre et vérifie que \
ta sortie respecte le format demandé du premier au dernier caractère.\
"""


def _needs_reinforcement(provider: str, model: str) -> bool:
    """Petits modèles locaux → directives répétées. Ollama toujours ; les autres
    providers OpenAI-compatibles pointés vers un modèle visiblement petit aussi."""
    if provider == "ollama":
        return True
    m = (model or "").lower()
    # Heuristique : tailles de petits modèles dans le nom (llama3.1:8b, mistral-7b…)
    return any(tag in m for tag in ("3b", "7b", "8b", "9b", "mini", "tiny", "small"))


def adapt_system(system: str, task: str | None = None,
                 provider: str = "anthropic", model: str = "") -> str:
    """Adapte le prompt système au moteur cible.

    - Anthropic (Claude / Fable 5) : retour INCHANGÉ — comportement actuel préservé.
    - Autres moteurs : préambule (rôle de la tâche + règles de format), puis le
      system d'origine sous un séparateur clair. Le system d'origine n'est
      jamais modifié ni tronqué.
    """
    p = (provider or "anthropic").strip().lower()
    if p in ("", "anthropic"):
        return system

    parts: list[str] = []
    role = TASK_ROLES.get((task or "").strip())
    if role:
        parts.append("RÔLE : " + role)
    parts.append(_FORMAT_RULES)
    if _needs_reinforcement(p, model):
        parts.append(_SMALL_MODEL_RULES)
    preamble = "\n\n".join(parts)

    base = (system or "").strip()
    if not base:
        return preamble
    return preamble + "\n\n━━━ CONSIGNES DE LA TÂCHE ━━━\n\n" + base
