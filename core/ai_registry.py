"""Registre déclaratif des assistants IA de PANDORA.

Ce module ne réalise aucun appel réseau. Il centralise les groupes, moteurs, profils
optimisés et tâches afin que Cinéma, Live et le routeur utilisent la même source de
vérité. Les modèles découverts dynamiquement peuvent utiliser une clé moteur de la
forme ``provider:model-id`` sans modifier ce registre.
"""

from __future__ import annotations

import re


# ── Modèles Claude ACTUELS (mise à jour du 03/10/2026, demande Matthieu : « mets à
#    jour avec les nouvelles versions de Claude partout où on utilise Haiku, Sonnet,
#    Fable et Opus »). Référence API Anthropic au 25/09/2026 : Opus 5.5, Sonnet 5.5,
#    Fable 5.1 ; Haiku 4.5 reste le Haiku le plus récent. Identifiants EXACTS, sans
#    suffixe de date.
OPUS_MODEL = "claude-opus-5-5"
SONNET_MODEL = "claude-sonnet-5-5"
HAIKU_MODEL = "claude-haiku-4-5"
FABLE_MODEL = "claude-fable-5-1"
DEFAULT_CREATIVE_MODEL = OPUS_MODEL

#: Ancien modèle Claude → son successeur. Appliqué à la RÉSOLUTION : une config,
#: un choix par tâche ou un modèle découvert qui nomme l'ancien passe au nouveau,
#: sans réécrire le fichier de l'utilisateur. Aucun successeur n'est plus cher que
#: son prédécesseur (Opus 5.5 : 4 $ / 20 $ contre 5 $ / 25 $ pour Opus 4.8 et 5 ;
#: Sonnet 5.5 et Fable 5.1 au même prix que Sonnet 5 et Fable 5).
ANTHROPIC_SUCCESSORS: dict[str, str] = {
    "claude-opus-5": OPUS_MODEL,
    "claude-opus-4-8": OPUS_MODEL,
    "claude-opus-4-7": OPUS_MODEL,
    "claude-opus-4-6": OPUS_MODEL,
    "claude-opus-4-5": OPUS_MODEL,
    "claude-opus-4-1": OPUS_MODEL,
    "claude-opus-4-0": OPUS_MODEL,
    "claude-opus-4": OPUS_MODEL,
    "claude-sonnet-5": SONNET_MODEL,
    "claude-sonnet-4-6": SONNET_MODEL,
    "claude-sonnet-4-5": SONNET_MODEL,
    "claude-sonnet-4-0": SONNET_MODEL,
    "claude-sonnet-4": SONNET_MODEL,
    "claude-3-7-sonnet": SONNET_MODEL,
    "claude-3-5-sonnet": SONNET_MODEL,
    "claude-fable-5": FABLE_MODEL,
    "claude-3-5-haiku": HAIKU_MODEL,
    "claude-3-haiku": HAIKU_MODEL,
}

_DATE_SUFFIX = re.compile(r"-(?:\d{8}|latest)$")


def current_model(model: str) -> str:
    """Le modèle Claude ACTUEL pour un identifiant donné (successeur si remplacé).

    Tolère les instantanés datés (« claude-sonnet-4-5-20250929 ») et les alias
    « -latest ». Un modèle inconnu ou déjà actuel est rendu tel quel."""
    raw = (model or "").strip()
    low = raw.lower()
    if not low.startswith("claude"):
        return raw
    if low in ANTHROPIC_SUCCESSORS:
        return ANTHROPIC_SUCCESSORS[low]
    base = _DATE_SUFFIX.sub("", low)
    return ANTHROPIC_SUCCESSORS.get(base, raw)


def is_superseded(model: str) -> bool:
    return current_model(model) != (model or "").strip()


_NAME_RE = re.compile(r"^claude-(opus|sonnet|haiku|fable|mythos)-(\d+)(?:-(\d{1,2}))?(?:-\d{8})?$")


def anthropic_display_name(model: str) -> str:
    """« claude-opus-5-5 » → « Claude Opus 5.5 » (repli lisible pour un modèle
    que le registre ne nomme pas, ex. un modèle découvert)."""
    m = _NAME_RE.match((model or "").strip().lower())
    if not m:
        return (model or "").strip() or "Claude"
    family, major, minor = m.groups()
    return f"Claude {family.capitalize()} {major}" + (f".{minor}" if minor else "")


GROUPS = (
    ("anthropic", "Anthropic"),
    ("openai", "ChatGPT / OpenAI"),
    # Les IA qui tournent SUR la machine (Ollama, LM Studio, llama.cpp, vLLM,
    # Jan…) : un groupe à elles depuis le 24/09/2026 — voir core/local_llm.
    ("local", "Local — sur votre machine"),
    ("experimental", "Expérimental"),
)

TASKS: list[tuple[str, str]] = [
    ("enhance",         "Amélioration des prompts"),
    ("storyboard_chat", "Chat du Storyboard"),
    ("assistant",       "Assistant / guide complet"),
    ("storyboard_gen",  "Génération du storyboard"),
    ("screenplay",      "Scénario (mise en page, arrangement)"),
    ("decoupage",       "Découpage PANDORA (plans)"),
    ("extraction",      "Extraction d'éléments (personnages, décors…)"),
    ("sync",            "Synchronisation du storyboard"),
    ("translate",       "Traduction des prompts (FR → EN/ZH)"),
    ("video_prompt",    "Prompt final (storyboard → moteur)"),
    ("element_chat",    "Direction artistique des éléments"),
    ("vision",          "Analyse visuelle"),
]


# ``model`` est le modèle créatif. Le tier utilitaire peut être remplacé par
# ``utility_model``. Les anciennes clés (claude, gpt…) restent valides.
ENGINES: dict[str, dict] = {
    # Les CLÉS (« claude », « opus », « fable5 »…) restent celles qu'enregistrent
    # les configs et les choix par tâche ; seuls les modèles changent.
    "claude":       {"group": "anthropic", "provider": "anthropic", "model": SONNET_MODEL, "utility_model": HAIKU_MODEL, "name": "Claude Sonnet 5.5"},
    "opus":         {"group": "anthropic", "provider": "anthropic", "model": OPUS_MODEL,   "utility_model": HAIKU_MODEL, "name": "Claude Opus 5.5"},
    "haiku":        {"group": "anthropic", "provider": "anthropic", "model": HAIKU_MODEL,  "utility_model": HAIKU_MODEL, "name": "Claude Haiku 4.5"},
    "fable5":       {"group": "anthropic", "provider": "anthropic", "model": FABLE_MODEL,  "utility_model": FABLE_MODEL, "name": "Claude Fable 5.1"},
    "openai_sol":   {"group": "openai", "provider": "openai", "model": "gpt-5.6-sol",   "utility_model": "gpt-5.6-sol",   "name": "GPT-5.6 Sol"},
    "openai_terra": {"group": "openai", "provider": "openai", "model": "gpt-5.6-terra", "utility_model": "gpt-5.6-terra", "name": "GPT-5.6 Terra"},
    "openai_luna":  {"group": "openai", "provider": "openai", "model": "gpt-5.6-luna",  "utility_model": "gpt-5.6-luna",  "name": "GPT-5.6 Luna"},
    "gpt":          {"group": "openai", "provider": "openai", "model": "gpt-5.5",       "utility_model": "gpt-5.5",       "name": "GPT-5.5"},
    # Forfait ChatGPT Plus / Pro par « Sign in with ChatGPT » (04/10/2026,
    # api/chatgpt_plan) : aucune clé, le modèle vient du catalogue DU COMPTE
    # (config « chatgpt_model », choisi dans les Paramètres).
    "chatgpt_plan": {"group": "openai", "provider": "chatgpt", "model": "", "utility_model": "", "name": "Compte ChatGPT (forfait Plus / Pro)"},
    "mistral":      {"group": "experimental", "provider": "mistral", "model": "mistral-large-latest", "utility_model": "mistral-small-latest", "name": "Mistral"},
    "kimi":         {"group": "experimental", "provider": "kimi", "model": "kimi-k2.7-code", "name": "Kimi"},
    "glm":          {"group": "experimental", "provider": "glm", "model": "glm-4.7", "name": "GLM"},
    "ollama":       {"group": "local", "provider": "ollama", "model": "llama3.1", "name": "Ollama local"},
    # Serveur OpenAI-compatible LOCAL (préréglages LM Studio / llama.cpp / vLLM /
    # Jan dans core/local_llm) : le modèle vient de la config (local_model).
    "local":        {"group": "local", "provider": "local", "model": "", "name": "Serveur IA local (LM Studio, llama.cpp, vLLM, Jan…)"},
    "custom":       {"group": "experimental", "provider": "custom", "model": "", "name": "Fournisseur personnalisé"},
}

ENGINE_ORDER = [
    "opus", "claude", "haiku", "fable5",
    "openai_sol", "openai_terra", "openai_luna", "gpt", "chatgpt_plan",
    "mistral", "kimi", "glm", "ollama", "local", "custom",
]

#: Fournisseurs qui tournent sur la machine (aucune clé, aucun crédit).
LOCAL_PROVIDERS = ("ollama", "local")


ANTHROPIC_OPTIMIZED: dict[str, str] = {
    "storyboard_gen": "opus",
    "screenplay": "claude",
    # Le Découpage est devenu le PIVOT créatif du pipeline (le storyboard en est
    # une conversion déterministe 1 plan = 1 fiche depuis 2026-07-22) → modèle de
    # tête. Opus et pas Fable : décision Matthieu 2026-07-23 (crédits) — Opus 5.5
    # depuis le 03/10/2026, Fable 5.1 coûte toujours 2,5 × plus cher.
    "decoupage": "opus",
    "sync": "claude",
    "storyboard_chat": "claude",
    "extraction": "claude",
    "enhance": "haiku",
    "assistant": "claude",
    "translate": "haiku",
    "video_prompt": "claude",
    "element_chat": "claude",
    "vision": "haiku",
}

# Profil demandé par Matthieu : aucune tâche ne sort d'OpenAI.
OPENAI_OPTIMIZED: dict[str, str] = {
    "storyboard_gen": "openai_sol",
    "screenplay": "openai_sol",
    "decoupage": "openai_sol",
    "video_prompt": "openai_sol",
    "storyboard_chat": "openai_terra",
    "assistant": "openai_terra",
    "sync": "openai_terra",
    "extraction": "openai_terra",
    "enhance": "openai_luna",
    "translate": "openai_luna",
    "element_chat": "openai_terra",
    "vision": "openai_terra",
}

PROFILES: dict[str, dict] = {
    "anthropic_optimized": {
        "name": "Anthropic optimisé par tâche",
        "group": "anthropic",
        "tasks": ANTHROPIC_OPTIMIZED,
    },
    "openai_optimized": {
        "name": "ChatGPT optimisé par tâche",
        "group": "openai",
        "tasks": OPENAI_OPTIMIZED,
    },
}

# Compatibilité avec les imports historiques de core.ai_provider.
TASK_DEFAULTS = ANTHROPIC_OPTIMIZED
PANDORA_OPTIMIZED = ANTHROPIC_OPTIMIZED


def dynamic_engine(provider: str, model: str) -> dict:
    """Crée une fiche moteur pour un modèle retourné par une API ``/models``."""
    provider = (provider or "").strip().lower()
    model = (model or "").strip()
    if provider in ("anthropic", "openai"):
        group = provider
    elif provider == "chatgpt":
        group = "openai"
    elif provider in LOCAL_PROVIDERS:
        group = "local"
    else:
        group = "experimental"
    return {"group": group, "provider": provider, "model": model,
            "utility_model": model, "name": model}


def engine(key: str, cfg: dict | None = None) -> dict | None:
    """Résout une clé statique ou dynamique ``provider:model-id``."""
    if key in ENGINES:
        item = dict(ENGINES[key])
    elif ":" in (key or ""):
        provider, model = key.split(":", 1)
        item = dynamic_engine(provider, model)
    else:
        return None
    cfg = cfg or {}
    provider = item["provider"]
    configured = {
        "openai": cfg.get("openai_model"),
        "kimi": cfg.get("kimi_model"),
        "glm": cfg.get("glm_model"),
        "ollama": cfg.get("ollama_model"),
        "local": cfg.get("local_model"),
        "custom": cfg.get("custom_model"),
        "chatgpt": cfg.get("chatgpt_model"),
    }.get(provider)
    if configured and key in ("gpt", "kimi", "glm", "ollama", "local", "custom",
                              "chatgpt_plan"):
        item["model"] = str(configured).strip()
        item["utility_model"] = item["model"]
    if provider == "anthropic":
        # Un ancien modèle Claude enregistré (choix par tâche « anthropic:claude-
        # opus-4-8 », moteur découvert…) passe à son successeur.
        item["model"] = current_model(item.get("model", ""))
        item["utility_model"] = current_model(item.get("utility_model", "")) or item["model"]
        if ":" in (key or ""):
            item["name"] = anthropic_display_name(item["model"])
    return item


def profile_from_config(cfg: dict) -> str:
    """Profil explicite, avec migration transparente des anciennes configs."""
    profile = (cfg.get("ai_profile") or "").strip()
    if profile in PROFILES or profile in ("single", "custom"):
        return profile
    provider = (cfg.get("ai_provider") or "anthropic").strip().lower()
    creative = (cfg.get("ai_model_creative") or "").strip()
    if provider in ("pandora", ""):
        return "anthropic_optimized"
    # Le défaut historique (Opus 4.8) comme l'actuel (Opus 5.5) désignent le profil
    # optimisé : current_model() ramène l'un à l'autre.
    if provider == "anthropic" and current_model(creative) in ("", DEFAULT_CREATIVE_MODEL):
        return "anthropic_optimized"
    if provider == "custom":
        return "custom"
    return "single"


def _legacy_single_engine(cfg: dict) -> dict:
    provider = (cfg.get("ai_provider") or "anthropic").strip().lower()
    model = (cfg.get("ai_model_creative") or "").strip()
    if provider == "openai":
        model = (cfg.get("openai_model") or model or "gpt-5.5").strip()
    elif provider == "mistral":
        model = "mistral-large-latest"
    elif provider == "kimi":
        model = (cfg.get("kimi_model") or "kimi-k2.7-code").strip()
    elif provider == "glm":
        model = (cfg.get("glm_model") or "glm-4.7").strip()
    elif provider == "ollama":
        model = (cfg.get("ollama_model") or "llama3.1").strip()
    elif provider == "local":
        model = (cfg.get("local_model") or "").strip()
    elif provider == "custom":
        model = (cfg.get("custom_model") or "").strip()
    elif provider == "chatgpt":
        model = (cfg.get("chatgpt_model") or "").strip()
    else:
        provider = "anthropic"
        model = current_model(model or DEFAULT_CREATIVE_MODEL)
    item = dynamic_engine(provider, model)
    if provider == "anthropic":
        item["name"] = anthropic_display_name(model)
    return item


def resolve_engine(cfg: dict, task: str | None = None) -> dict:
    """Résout le moteur effectif sans repli inter-fournisseur silencieux."""
    profile_key = profile_from_config(cfg)
    profile = PROFILES.get(profile_key)
    overrides = cfg.get("ai_task_engines") or {}
    if task and overrides.get(task):
        item = engine(str(overrides[task]), cfg)
        # Un profil optimisé est une frontière stricte de fournisseur. Une ancienne
        # configuration peut encore contenir des overrides Claude alors que le profil
        # ChatGPT vient d'être sélectionné (ou inversement) : ils ne doivent jamais
        # permettre une sortie silencieuse de la famille choisie.
        if item and (not profile or item.get("group") == profile.get("group")):
            return item

    if profile and task:
        item = engine(profile["tasks"].get(task, ""), cfg)
        if item:
            return item

    selected_key = (cfg.get("ai_engine") or "").strip()
    if selected_key:
        item = engine(selected_key, cfg)
        if item:
            return item
    return _legacy_single_engine(cfg)


def recommended_engine_name(task: str, profile: str = "anthropic_optimized") -> str:
    spec = PROFILES.get(profile) or PROFILES["anthropic_optimized"]
    item = engine(spec["tasks"].get(task, ""))
    return item["name"] if item else "Assistant IA"


def primary_menu_items(discovered: dict[str, list[str]] | None = None) -> list[dict]:
    """Items du sélecteur principal, groupes inclus et non sélectionnables."""
    discovered = discovered or {}
    rows: list[dict] = []
    static_by_group = {
        "anthropic": ["opus", "claude", "haiku", "fable5"],
        "openai": ["openai_sol", "openai_terra", "openai_luna", "gpt", "chatgpt_plan"],
        "local": ["ollama", "local"],
        "experimental": ["mistral", "kimi", "glm", "custom"],
    }
    providers_by_group = {
        "local": LOCAL_PROVIDERS,
        "experimental": ("mistral", "kimi", "glm", "custom"),
    }
    profile_by_group = {
        "anthropic": "anthropic_optimized",
        "openai": "openai_optimized",
    }
    for group_key, group_label in GROUPS:
        rows.append({"label": group_label, "selectable": False, "group": group_key})
        if group_key in profile_by_group:
            pk = profile_by_group[group_key]
            rows.append({"label": PROFILES[pk]["name"], "selectable": True,
                         "profile": pk, "engine": ""})
        seen = set()
        for key in static_by_group[group_key]:
            item = engine(key)
            seen.add(item["model"])
            rows.append({"label": item["name"], "selectable": True,
                         "profile": "custom" if key == "custom" else "single",
                         "engine": key})
        providers = providers_by_group.get(group_key, (group_key,))
        for provider in providers:
            for model in discovered.get(provider, []) or []:
                if model in seen:
                    continue
                # Un modèle Claude remplacé (Opus 4.8, Sonnet 5, Fable 5…) n'est
                # plus proposé : le choisir donnerait de toute façon son successeur.
                if provider == "anthropic" and is_superseded(model):
                    continue
                seen.add(model)
                rows.append({"label": model, "selectable": True, "profile": "single",
                             "engine": f"{provider}:{model}"})
    return rows
