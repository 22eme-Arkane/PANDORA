"""Registre déclaratif des assistants IA de PANDORA.

Ce module ne réalise aucun appel réseau. Il centralise les groupes, moteurs, profils
optimisés et tâches afin que Cinéma, Live et le routeur utilisent la même source de
vérité. Les modèles découverts dynamiquement peuvent utiliser une clé moteur de la
forme ``provider:model-id`` sans modifier ce registre.
"""

from __future__ import annotations


GROUPS = (
    ("anthropic", "Anthropic"),
    ("openai", "ChatGPT / OpenAI"),
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
    ("video_prompt",    "Prompt vidéo Seedance (prose anglaise)"),
    ("element_chat",    "Direction artistique des éléments"),
    ("vision",          "Analyse visuelle"),
]


# ``model`` est le modèle créatif. Le tier utilitaire peut être remplacé par
# ``utility_model``. Les anciennes clés (claude, gpt…) restent valides.
ENGINES: dict[str, dict] = {
    "claude":       {"group": "anthropic", "provider": "anthropic", "model": "claude-sonnet-5",  "utility_model": "claude-haiku-4-5", "name": "Claude Sonnet 5"},
    "opus":         {"group": "anthropic", "provider": "anthropic", "model": "claude-opus-4-8",  "utility_model": "claude-haiku-4-5", "name": "Claude Opus 4.8"},
    "haiku":        {"group": "anthropic", "provider": "anthropic", "model": "claude-haiku-4-5", "utility_model": "claude-haiku-4-5", "name": "Claude Haiku 4.5"},
    "fable5":       {"group": "anthropic", "provider": "anthropic", "model": "claude-fable-5",   "utility_model": "claude-fable-5",   "name": "Fable 5"},
    "openai_sol":   {"group": "openai", "provider": "openai", "model": "gpt-5.6-sol",   "utility_model": "gpt-5.6-sol",   "name": "GPT-5.6 Sol"},
    "openai_terra": {"group": "openai", "provider": "openai", "model": "gpt-5.6-terra", "utility_model": "gpt-5.6-terra", "name": "GPT-5.6 Terra"},
    "openai_luna":  {"group": "openai", "provider": "openai", "model": "gpt-5.6-luna",  "utility_model": "gpt-5.6-luna",  "name": "GPT-5.6 Luna"},
    "gpt":          {"group": "openai", "provider": "openai", "model": "gpt-5.5",       "utility_model": "gpt-5.5",       "name": "GPT-5.5"},
    "mistral":      {"group": "experimental", "provider": "mistral", "model": "mistral-large-latest", "utility_model": "mistral-small-latest", "name": "Mistral"},
    "kimi":         {"group": "experimental", "provider": "kimi", "model": "kimi-k2.7-code", "name": "Kimi"},
    "glm":          {"group": "experimental", "provider": "glm", "model": "glm-4.7", "name": "GLM"},
    "ollama":       {"group": "experimental", "provider": "ollama", "model": "llama3.1", "name": "Ollama local"},
    "custom":       {"group": "experimental", "provider": "custom", "model": "", "name": "Fournisseur personnalisé"},
}

ENGINE_ORDER = [
    "opus", "claude", "haiku", "fable5",
    "openai_sol", "openai_terra", "openai_luna", "gpt",
    "mistral", "kimi", "glm", "ollama", "custom",
]


ANTHROPIC_OPTIMIZED: dict[str, str] = {
    "storyboard_gen": "opus",
    "screenplay": "claude",
    # Le Découpage est devenu le PIVOT créatif du pipeline (le storyboard en est
    # une conversion déterministe 1 plan = 1 fiche depuis 2026-07-22) → modèle de
    # tête. Opus 4.8 et pas Fable 5 : décision Matthieu 2026-07-23 (crédits).
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
    group = provider if provider in ("anthropic", "openai") else "experimental"
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
        "custom": cfg.get("custom_model"),
    }.get(provider)
    if configured and key in ("gpt", "kimi", "glm", "ollama", "custom"):
        item["model"] = str(configured).strip()
        item["utility_model"] = item["model"]
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
    if provider == "anthropic" and creative in ("", "claude-opus-4-8"):
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
    elif provider == "custom":
        model = (cfg.get("custom_model") or "").strip()
    else:
        provider = "anthropic"
        model = model or "claude-opus-4-8"
    return dynamic_engine(provider, model)


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
        "openai": ["openai_sol", "openai_terra", "openai_luna", "gpt"],
        "experimental": ["mistral", "kimi", "glm", "ollama", "custom"],
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
        providers = (group_key,) if group_key != "experimental" else (
            "mistral", "kimi", "glm", "ollama", "custom")
        for provider in providers:
            for model in discovered.get(provider, []) or []:
                if model in seen:
                    continue
                seen.add(model)
                rows.append({"label": model, "selectable": True, "profile": "single",
                             "engine": f"{provider}:{model}"})
    return rows
