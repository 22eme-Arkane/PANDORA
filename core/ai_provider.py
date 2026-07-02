"""
core/ai_provider.py — Couche d'abstraction des assistants IA texte (Cinéma + Live).

Tous les appels IA TEXTE de PANDORA passent par ce module : le fournisseur et le
modèle se choisissent dans Paramètres (config.json). Les appels VISION (analyse
d'images : références visuelles, portraits Nano Banana, style ref) restent sur
Anthropic — les autres fournisseurs gèrent la vision différemment (hors périmètre v1).

Config (config.json) :
    "ai_provider"        : "anthropic" (défaut) | "openai" | "mistral" | "kimi" | "ollama"
    "ai_model_creative"  : modèle du tier créatif Anthropic (défaut "claude-opus-4-8" ; Sonnet 5 = "claude-sonnet-5" ;
                           "claude-fable-5" pour Fable 5)
    "anthropic_key"      : clé API Anthropic (Claude / Fable 5)
    "openai_key"         : clé API OpenAI (GPT-5.5)
    "openai_model"       : modèle OpenAI (défaut "gpt-5.5")
    "mistral_key"        : clé API Mistral
    "kimi_key"           : clé API Kimi / Moonshot (sk-…) — facultative si URL locale
    "kimi_url"           : URL de base OpenAI-compatible (défaut https://api.moonshot.ai/v1 ;
                           pour du LOCAL, pointer vers ex. http://localhost:11434/v1)
    "kimi_model"         : modèle Kimi (défaut "kimi-k2.7-code")
    "glm_key"            : clé API GLM / Zhipu — facultative si URL locale
    "glm_url"            : URL de base OpenAI-compatible (défaut
                           https://open.bigmodel.cn/api/paas/v4 ; pour du LOCAL,
                           pointer vers ex. http://localhost:11434/v1)
    "glm_model"          : modèle GLM (défaut "glm-4.7")
    "ollama_url"         : URL du serveur Ollama (défaut http://localhost:11434)
    "ollama_model"       : modèle Ollama (défaut "llama3.1")
    "ai_task_engines"    : {task_key: engine_key} — moteur par tâche (override du défaut)

Moteurs (engine_key) — granularité du choix par tâche :
    "claude" · "fable5" · "gpt" · "mistral" · "kimi" · "glm" · "ollama"

Kimi K2.7 (Moonshot AI) — API officielle compatible OpenAI (base /v1, Bearer key).
Modèle par défaut "kimi-k2.7-code". L'URL de base étant éditable, le MÊME moteur
sert l'API cloud (Moonshot) OU un serveur local OpenAI-compatible (Ollama /v1,
llama.cpp, LM Studio) — d'où « API ou local » sans deux moteurs distincts.

GLM 4.7 (Zhipu AI) — même modèle d'intégration que Kimi : API OpenAI-compatible
(défaut cloud Zhipu https://open.bigmodel.cn/api/paas/v4), URL de base éditable
→ le même moteur sert l'API cloud OU un serveur local (vLLM, Ollama /v1…).

Prompts système PAR MOTEUR : core/engine_prompts.adapt_system est appliqué au
point central (chat / chat_stream / stream) — identité pour Anthropic, préambule
de discipline (format JSON brut, marqueurs, langue) pour les autres moteurs.

Tiers de modèles :
    "utility"  — tâches rapides / peu chères : traduction, extractions JSON courtes
    "creative" — tâches longues / créatives : storyboard, arrangement, mise en page

API :
    complete(system, user, tier="utility", max_tokens=2048, task=None) -> str
    stream(system, user, on_chunk, tier="creative", max_tokens=4096, task=None) -> str
    chat(system, messages, tier="creative", max_tokens=2048, task=None) -> str
    key_error(task=None) -> str | None  # message d'erreur si la clé du fournisseur manque
    ai_name() -> str                    # nom d'affichage du moteur GLOBAL
"""

from __future__ import annotations


# ── Fournisseurs & moteurs ──────────────────────────────────────────────────────

_PROVIDERS = ("anthropic", "openai", "mistral", "kimi", "glm", "ollama")

# Moteur = (fournisseur, modèle créatif, nom d'affichage). Permet de choisir
# Claude vs Fable 5 (même fournisseur Anthropic, modèles différents) par tâche.
ENGINES: dict[str, dict] = {
    "claude":  {"provider": "anthropic", "creative_model": "claude-sonnet-5",   "name": "Claude Sonnet 5"},
    "opus":    {"provider": "anthropic", "creative_model": "claude-opus-4-8",   "name": "Claude Opus 4.8"},
    "haiku":   {"provider": "anthropic", "creative_model": "claude-haiku-4-5",  "name": "Claude Haiku 4.5"},
    "fable5":  {"provider": "anthropic", "creative_model": "claude-fable-5",    "name": "Fable 5"},
    "gpt":     {"provider": "openai",    "creative_model": "",                  "name": "GPT-5.5"},
    "mistral": {"provider": "mistral",   "creative_model": "",                  "name": "Mistral"},
    "kimi":    {"provider": "kimi",      "creative_model": "",                  "name": "Kimi K2.7"},
    "glm":     {"provider": "glm",       "creative_model": "",                  "name": "GLM 4.7"},
    "ollama":  {"provider": "ollama",    "creative_model": "",                  "name": "Ollama"},
}

# Ordre d'affichage des moteurs dans les menus (Paramètres avancés).
ENGINE_ORDER = ["claude", "opus", "haiku", "fable5", "gpt", "mistral", "kimi", "glm", "ollama"]

# Tâches IA paramétrables individuellement (Paramètres → Assistant IA → avancés).
# (clé, libellé FR). Chaque appelant passe task=<clé> ; sans override → moteur global.
TASKS: list[tuple[str, str]] = [
    ("enhance",         "Amélioration des prompts"),
    ("storyboard_chat", "Chat du Storyboard"),
    ("assistant",       "Assistant / guide complet"),
    ("storyboard_gen",  "Génération du storyboard"),
    ("screenplay",      "Scénario (mise en page, arrangement)"),
    ("extraction",      "Extraction d'éléments (personnages, décors…)"),
    ("sync",            "Synchronisation du storyboard"),
    ("translate",       "Traduction des prompts (FR → EN/ZH)"),
]

# Modèle par défaut (créatif) — Opus 4.8.
_DEFAULT_CREATIVE = "claude-opus-4-8"

# ── Moteur IDÉAL par tâche (profil « PANDORA optimisé » = DÉFAUT) ───────────────
# Objectif : le MOINS de crédits possible, sans IA surdimensionnée. Seul le prompt
# du storyboard reste sur Opus 4.8 (précision maximale exigée — découpage). Le reste
# descend en Sonnet (équilibré) ou Haiku (économe). NB : les appels du tier utilitaire
# (traduction, extractions courtes, chat) restent de toute façon sur Haiku via _model().
TASK_DEFAULTS: dict[str, str] = {
    "storyboard_gen":  "opus",    # découpage / prompts du storyboard — précision MAX
    "screenplay":      "claude",  # scénario (mise en page, arrangement) — Sonnet 5
    "sync":            "claude",  # synchronisation storyboard — Sonnet 5
    "storyboard_chat": "claude",  # chat storyboard — Sonnet 5 (éditions JSON fiables)
    "extraction":      "claude",  # extraction JSON (persos/décors…) — Sonnet 5 (précision)
    "enhance":         "haiku",   # amélioration de prompt — Haiku (économe)
    "assistant":       "claude",  # guide / assistant — Sonnet 5 (qualité des réponses)
    "translate":       "haiku",   # traduction FR→EN/ZH — Haiku (économe)
}

# « PANDORA optimisé » = ce mapping (alias conservé pour les Paramètres).
PANDORA_OPTIMIZED: dict[str, str] = dict(TASK_DEFAULTS)


def recommended_engine_name(task: str) -> str:
    """Nom du moteur conseillé pour une tâche (pour les libellés « Par défaut »)."""
    e = ENGINES.get(TASK_DEFAULTS.get(task, ""))
    return e["name"] if e else "Claude"

_ANTHROPIC_UTILITY = "claude-haiku-4-5"
_MISTRAL_MODELS = {"utility": "mistral-small-latest", "creative": "mistral-large-latest"}
_OPENAI_MODELS  = {"utility": "gpt-5.5", "creative": "gpt-5.5"}
# Kimi K2.7 (Moonshot) — un seul modèle pour les deux tiers (comme GPT/Ollama).
_KIMI_DEFAULT_MODEL = "kimi-k2.7-code"
_KIMI_DEFAULT_URL   = "https://api.moonshot.ai/v1"
# GLM 4.7 (Zhipu) — même schéma que Kimi : OpenAI-compatible, URL éditable (cloud ou local).
_GLM_DEFAULT_MODEL = "glm-4.7"
_GLM_DEFAULT_URL   = "https://open.bigmodel.cn/api/paas/v4"


# ── Config ────────────────────────────────────────────────────────────────────

def _cfg() -> dict:
    from core.config import load_config
    return load_config()


def get_provider() -> str:
    """Fournisseur GLOBAL (défaut quand une tâche n'a pas d'override)."""
    p = (_cfg().get("ai_provider") or "anthropic").strip().lower()
    return p if p in _PROVIDERS else "anthropic"


def get_creative_model() -> str:
    """Modèle du tier créatif chez Anthropic (Sonnet par défaut, Fable 5 en option)."""
    m = (_cfg().get("ai_model_creative") or "").strip()
    return m or _DEFAULT_CREATIVE


def _resolve_engine(task: str | None = None) -> tuple[str, str]:
    """Renvoie (provider, creative_model) pour une tâche.

    Priorité : (1) override explicite par tâche (Choix personnalisé) ; (2) sinon, si
    l'utilisateur est sur le profil PAR DÉFAUT (« PANDORA optimisé » : Anthropic + Opus,
    ou provider « pandora »), on route chaque tâche vers son moteur IDÉAL (TASK_DEFAULTS)
    → le moins de crédits, Opus seulement pour le storyboard ; (3) sinon, le moteur
    GLOBAL choisi explicitement (Sonnet / Haiku / Fable 5 / GPT / Mistral / Ollama)
    s'applique partout. Ne dégrade jamais un choix explicite de l'utilisateur."""
    cfg = _cfg()
    if task:
        eng_key = (cfg.get("ai_task_engines") or {}).get(task)
        if eng_key and eng_key in ENGINES:
            e = ENGINES[eng_key]
            return e["provider"], e["creative_model"]
    provider = (cfg.get("ai_provider") or "anthropic").strip().lower()
    creative = (cfg.get("ai_model_creative") or "").strip()
    # Profil par défaut = routage idéal par tâche (économe, Opus pour le storyboard).
    # « custom » (Choix personnalisé) : les tâches SANS override affichent
    # « Par défaut · X » dans les Paramètres → elles doivent résoudre pareil.
    _is_smart_default = (provider in ("pandora", "custom", "")
                         or (provider == "anthropic" and creative in ("", _DEFAULT_CREATIVE)))
    if _is_smart_default and task and task in TASK_DEFAULTS:
        e = ENGINES[TASK_DEFAULTS[task]]
        return e["provider"], e["creative_model"]
    if provider not in _PROVIDERS:
        provider = "anthropic"
    return provider, (creative or _DEFAULT_CREATIVE)


def _model(tier: str, provider: str | None = None, creative_model: str = "") -> str:
    # provider=None → moteur global (rétro-compatible avec les anciens appels)
    if provider is None:
        provider, creative_model = _resolve_engine()
    if provider == "anthropic":
        return (creative_model or _DEFAULT_CREATIVE) if tier == "creative" else _ANTHROPIC_UTILITY
    if provider == "openai":
        m = (_cfg().get("openai_model") or "").strip()
        return m or _OPENAI_MODELS["creative" if tier == "creative" else "utility"]
    if provider == "mistral":
        return _MISTRAL_MODELS["creative" if tier == "creative" else "utility"]
    if provider == "kimi":
        m = (_cfg().get("kimi_model") or "").strip()
        return m or _KIMI_DEFAULT_MODEL
    if provider == "glm":
        m = (_cfg().get("glm_model") or "").strip()
        return m or _GLM_DEFAULT_MODEL
    if provider == "ollama":
        return (_cfg().get("ollama_model") or "llama3.1").strip() or "llama3.1"
    return creative_model or _DEFAULT_CREATIVE


# ── Nom d'affichage du moteur global ────────────────────────────────────────────

_NAME_CACHE: str | None = None


def ai_name() -> str:
    """Nom d'affichage du moteur GLOBAL — pour les libellés UI dynamiques.
    Mis en cache ; les Paramètres appellent refresh_name_cache() après sauvegarde."""
    global _NAME_CACHE
    if _NAME_CACHE is None:
        provider = get_provider()
        if provider == "anthropic":
            _NAME_CACHE = "Fable 5" if "fable" in get_creative_model() else "Claude"
        elif provider == "openai":
            _NAME_CACHE = "GPT-5.5"
        else:
            _NAME_CACHE = {"mistral": "Mistral", "kimi": "Kimi K2.7",
                           "glm": "GLM 4.7",
                           "ollama": "Ollama"}.get(provider, provider.capitalize())
    return _NAME_CACHE


def refresh_name_cache() -> None:
    global _NAME_CACHE
    _NAME_CACHE = None


def brand(text: str) -> str:
    """Remplace « Claude » par le nom du moteur global dans un libellé UI.
    À appliquer APRÈS translate()."""
    n = ai_name()
    return text if n == "Claude" else text.replace("Claude", n)


def humanize_ai_error(msg: str) -> str:
    """Message d'erreur API TEXTE (Anthropic/OpenAI…) lisible pour l'utilisateur.

    Les erreurs brutes (JSON) sont opaques ; les cas fréquents — crédits
    épuisés, quota, clé invalide — méritent une phrase claire. Retourne le
    message d'origine si le cas n'est pas reconnu.
    (Pendant fal.ai : core.worker.humanize_api_error — ne pas fusionner, les
    consignes de recharge diffèrent.)"""
    from core.i18n import translate as _tr
    low = (msg or "").lower()
    if ("credit balance" in low or "insufficient credit" in low
            or ("billing" in low and "credit" in low)):
        return _tr("Crédits API épuisés — recharge ton compte "
                   "(console.anthropic.com → Billing) puis relance. "
                   "La dernière analyse sauvegardée reste disponible.")
    if "rate limit" in low or "429" in low or "overloaded" in low or "529" in low:
        return _tr("Service IA saturé ou limite de débit atteinte — "
                   "réessaie dans quelques instants.")
    if "401" in low or "authentication" in low or "invalid x-api-key" in low:
        return _tr("Clé API invalide — vérifie-la dans Paramètres → Clés API.")
    return msg


def _engine_display_name(provider: str, creative_model: str) -> str:
    """Nom d'affichage lisible d'un moteur résolu (provider + modèle créatif).
    Pour Anthropic, distingue Opus / Sonnet / Haiku / Fable 5."""
    if provider == "anthropic":
        for e in ENGINES.values():
            if e["provider"] == "anthropic" and e["creative_model"] == creative_model:
                return e["name"]
        cm = creative_model or _DEFAULT_CREATIVE
        if "opus" in cm:
            return "Claude Opus 4.8"
        if "fable" in cm:
            return "Fable 5"
        if "haiku" in cm:
            return "Claude Haiku 4.5"
        return "Claude Sonnet 5"
    if provider == "openai":
        return ENGINES["gpt"]["name"]
    if provider == "mistral":
        return ENGINES["mistral"]["name"]
    if provider == "kimi":
        return ENGINES["kimi"]["name"]
    if provider == "glm":
        return ENGINES["glm"]["name"]
    if provider == "ollama":
        return ENGINES["ollama"]["name"]
    return "Claude"


def ai_name_for_task(task: str | None = None) -> str:
    """Nom d'affichage PRÉCIS du moteur réellement utilisé pour une tâche : override
    par tâche s'il existe, sinon moteur global. Sert aux libellés UI dynamiques pour
    que l'utilisateur voie le modèle exact (ex. « Claude Opus 4.8 », « GPT-5.5 »)."""
    provider, creative = _resolve_engine(task)
    return _engine_display_name(provider, creative)


def key_error(task: str | None = None) -> str | None:
    """Message d'erreur si la clé/connexion du fournisseur (de la tâche) manque."""
    provider, _ = _resolve_engine(task)
    cfg = _cfg()
    if provider == "anthropic":
        if not cfg.get("anthropic_key", "").strip():
            return "Clé Anthropic (Claude / Fable 5) manquante — renseignez-la dans Paramètres."
        return None
    if provider == "openai":
        if not cfg.get("openai_key", "").strip():
            return "Clé OpenAI (GPT-5.5) manquante — renseignez-la dans Paramètres."
        return None
    if provider == "mistral":
        if not cfg.get("mistral_key", "").strip():
            return "Clé Mistral manquante — renseignez-la dans Paramètres."
        return None
    if provider == "kimi":
        # Clé exigée seulement pour l'API cloud ; une URL locale (Ollama /v1,
        # llama.cpp, LM Studio) ne demande pas de clé.
        url = (cfg.get("kimi_url") or _KIMI_DEFAULT_URL).strip().lower()
        is_local = ("localhost" in url) or ("127.0.0.1" in url)
        if not is_local and not cfg.get("kimi_key", "").strip():
            return ("Clé Kimi (Moonshot) manquante — renseignez-la dans Paramètres "
                    "(ou pointez l'URL Kimi vers un serveur local).")
        return None
    if provider == "glm":
        # Même logique que Kimi : clé exigée seulement pour l'API cloud Zhipu ;
        # une URL locale (vLLM, Ollama /v1…) ne demande pas de clé.
        url = (cfg.get("glm_url") or _GLM_DEFAULT_URL).strip().lower()
        is_local = ("localhost" in url) or ("127.0.0.1" in url)
        if not is_local and not cfg.get("glm_key", "").strip():
            return ("Clé GLM (Zhipu) manquante — renseignez-la dans Paramètres "
                    "(ou pointez l'URL GLM vers un serveur local).")
        return None
    if provider == "ollama":
        return None   # serveur local, pas de clé ; l'erreur réseau parlera d'elle-même
    return None


# ── Adaptateurs (reçoivent le MODÈLE résolu, donc indépendants du global) ────────

def _anthropic_client():
    import anthropic
    return anthropic.Anthropic(api_key=_cfg().get("anthropic_key", "").strip())


def _anthropic_extra(model: str) -> dict:
    """Sonnet 5 active la réflexion ADAPTATIVE quand `thinking` est OMIS (≠ Sonnet 4.6,
    qui ne réfléchissait pas) — cela rognerait les sorties à max_tokens serré
    (storyboard / scénario JSON). On la désactive donc explicitement pour préserver le
    comportement. EXCEPTION : Fable 5 / Mythos refusent `thinking:{disabled}` (400) →
    on omet le champ pour eux (réflexion toujours active)."""
    m = (model or "").lower()
    if "fable" in m or "mythos" in m:
        return {}
    return {"thinking": {"type": "disabled"}}


def _anthropic_complete(system, messages, model, max_tokens) -> str:
    msg = _anthropic_client().messages.create(
        model=model, max_tokens=max_tokens, system=system, messages=messages,
        **_anthropic_extra(model),
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def _anthropic_stream(system, messages, on_chunk, model, max_tokens) -> str:
    full = ""
    with _anthropic_client().messages.stream(
        model=model, max_tokens=max_tokens, system=system, messages=messages,
        **_anthropic_extra(model),
    ) as st:
        for t in st.text_stream:
            full += t
            if on_chunk:
                on_chunk(t)
    return full


def _openai_payload(system, messages, model, max_tokens, stream_flag) -> tuple:
    msgs = [{"role": "system", "content": system}] if system else []
    msgs += [{"role": m["role"], "content": m["content"]} for m in messages]
    return ("https://api.openai.com/v1/chat/completions", {
        "model": model, "max_completion_tokens": max_tokens,
        "messages": msgs, "stream": stream_flag,
    }, {"Authorization": f"Bearer {_cfg().get('openai_key', '').strip()}",
        "Content-Type": "application/json"})


def _openai_complete(system, messages, model, max_tokens) -> str:
    import requests
    url, payload, headers = _openai_payload(system, messages, model, max_tokens, False)
    r = requests.post(url, json=payload, headers=headers, timeout=300)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _openai_stream(system, messages, on_chunk, model, max_tokens) -> str:
    import json as _json
    import requests
    url, payload, headers = _openai_payload(system, messages, model, max_tokens, True)
    full = ""
    with requests.post(url, json=payload, headers=headers, timeout=300, stream=True) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line or not line.startswith(b"data:"):
                continue
            data = line[5:].strip()
            if data == b"[DONE]":
                break
            try:
                delta = _json.loads(data)["choices"][0]["delta"].get("content", "")
            except Exception:
                continue
            if delta:
                full += delta
                if on_chunk:
                    on_chunk(delta)
    return full


def _mistral_payload(system, messages, model, max_tokens, stream_flag) -> tuple:
    msgs = [{"role": "system", "content": system}] if system else []
    msgs += [{"role": m["role"], "content": m["content"]} for m in messages]
    return ("https://api.mistral.ai/v1/chat/completions", {
        "model": model, "max_tokens": max_tokens,
        "messages": msgs, "stream": stream_flag,
    }, {"Authorization": f"Bearer {_cfg().get('mistral_key', '').strip()}",
        "Content-Type": "application/json"})


def _mistral_complete(system, messages, model, max_tokens) -> str:
    import requests
    url, payload, headers = _mistral_payload(system, messages, model, max_tokens, False)
    r = requests.post(url, json=payload, headers=headers, timeout=300)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _mistral_stream(system, messages, on_chunk, model, max_tokens) -> str:
    import json as _json
    import requests
    url, payload, headers = _mistral_payload(system, messages, model, max_tokens, True)
    full = ""
    with requests.post(url, json=payload, headers=headers, timeout=300, stream=True) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line or not line.startswith(b"data:"):
                continue
            data = line[5:].strip()
            if data == b"[DONE]":
                break
            try:
                delta = _json.loads(data)["choices"][0]["delta"].get("content", "")
            except Exception:
                continue
            if delta:
                full += delta
                if on_chunk:
                    on_chunk(delta)
    return full


def _kimi_base_url() -> str:
    """URL de base OpenAI-compatible de Kimi (cloud Moonshot par défaut, ou local)."""
    return ((_cfg().get("kimi_url") or _KIMI_DEFAULT_URL).strip().rstrip("/"))


def _kimi_payload(system, messages, model, max_tokens, stream_flag) -> tuple:
    msgs = [{"role": "system", "content": system}] if system else []
    msgs += [{"role": m["role"], "content": m["content"]} for m in messages]
    # Bearer 'local' = jeton factice pour les serveurs locaux qui ignorent l'auth.
    key = _cfg().get("kimi_key", "").strip() or "local"
    return (f"{_kimi_base_url()}/chat/completions", {
        "model": model, "max_tokens": max_tokens,
        "messages": msgs, "stream": stream_flag,
    }, {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})


def _kimi_complete(system, messages, model, max_tokens) -> str:
    import requests
    url, payload, headers = _kimi_payload(system, messages, model, max_tokens, False)
    r = requests.post(url, json=payload, headers=headers, timeout=300)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _kimi_stream(system, messages, on_chunk, model, max_tokens) -> str:
    import json as _json
    import requests
    url, payload, headers = _kimi_payload(system, messages, model, max_tokens, True)
    full = ""
    with requests.post(url, json=payload, headers=headers, timeout=300, stream=True) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line or not line.startswith(b"data:"):
                continue
            data = line[5:].strip()
            if data == b"[DONE]":
                break
            try:
                # Kimi K2.7 est un modèle « thinking » : on ne garde que 'content'
                # (la réflexion est dans 'reasoning_content', ignorée volontairement).
                delta = _json.loads(data)["choices"][0]["delta"].get("content", "")
            except Exception:
                continue
            if delta:
                full += delta
                if on_chunk:
                    on_chunk(delta)
    return full


def _glm_base_url() -> str:
    """URL de base OpenAI-compatible de GLM (cloud Zhipu par défaut, ou local)."""
    return ((_cfg().get("glm_url") or _GLM_DEFAULT_URL).strip().rstrip("/"))


def _glm_payload(system, messages, model, max_tokens, stream_flag) -> tuple:
    msgs = [{"role": "system", "content": system}] if system else []
    msgs += [{"role": m["role"], "content": m["content"]} for m in messages]
    # Bearer 'local' = jeton factice pour les serveurs locaux qui ignorent l'auth
    # (même convention que Kimi).
    key = _cfg().get("glm_key", "").strip() or "local"
    return (f"{_glm_base_url()}/chat/completions", {
        "model": model, "max_tokens": max_tokens,
        "messages": msgs, "stream": stream_flag,
    }, {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})


def _glm_complete(system, messages, model, max_tokens) -> str:
    # RÉUTILISE le chemin OpenAI-compatible de Kimi : seul le payload
    # (URL de base + clé glm_*) diffère.
    import requests
    url, payload, headers = _glm_payload(system, messages, model, max_tokens, False)
    r = requests.post(url, json=payload, headers=headers, timeout=300)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _glm_stream(system, messages, on_chunk, model, max_tokens) -> str:
    import json as _json
    import requests
    url, payload, headers = _glm_payload(system, messages, model, max_tokens, True)
    full = ""
    with requests.post(url, json=payload, headers=headers, timeout=300, stream=True) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line or not line.startswith(b"data:"):
                continue
            data = line[5:].strip()
            if data == b"[DONE]":
                break
            try:
                # GLM 4.7 est un modèle « thinking » (comme Kimi K2.7) : on ne garde
                # que 'content' (la réflexion 'reasoning_content' est ignorée).
                delta = _json.loads(data)["choices"][0]["delta"].get("content", "")
            except Exception:
                continue
            if delta:
                full += delta
                if on_chunk:
                    on_chunk(delta)
    return full


def _ollama_url() -> str:
    return ((_cfg().get("ollama_url") or "http://localhost:11434").strip().rstrip("/"))


def _ollama_complete(system, messages, model, max_tokens) -> str:
    import requests
    msgs = ([{"role": "system", "content": system}] if system else []) + list(messages)
    r = requests.post(f"{_ollama_url()}/api/chat", json={
        "model": model, "messages": msgs, "stream": False,
        "options": {"num_predict": max_tokens},
    }, timeout=600)
    r.raise_for_status()
    return r.json().get("message", {}).get("content", "")


def _ollama_stream(system, messages, on_chunk, model, max_tokens) -> str:
    import json as _json
    import requests
    msgs = ([{"role": "system", "content": system}] if system else []) + list(messages)
    full = ""
    with requests.post(f"{_ollama_url()}/api/chat", json={
        "model": model, "messages": msgs, "stream": True,
        "options": {"num_predict": max_tokens},
    }, timeout=600, stream=True) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            try:
                chunk = _json.loads(line)
            except Exception:
                continue
            delta = chunk.get("message", {}).get("content", "")
            if delta:
                full += delta
                if on_chunk:
                    on_chunk(delta)
            if chunk.get("done"):
                break
    return full


# ── Dispatch ────────────────────────────────────────────────────────────────────

def _dispatch_complete(provider, system, messages, model, max_tokens) -> str:
    if provider == "openai":
        return _openai_complete(system, messages, model, max_tokens)
    if provider == "mistral":
        return _mistral_complete(system, messages, model, max_tokens)
    if provider == "kimi":
        return _kimi_complete(system, messages, model, max_tokens)
    if provider == "glm":
        return _glm_complete(system, messages, model, max_tokens)
    if provider == "ollama":
        return _ollama_complete(system, messages, model, max_tokens)
    return _anthropic_complete(system, messages, model, max_tokens)


def _dispatch_stream(provider, system, messages, on_chunk, model, max_tokens) -> str:
    if provider == "openai":
        return _openai_stream(system, messages, on_chunk, model, max_tokens)
    if provider == "mistral":
        return _mistral_stream(system, messages, on_chunk, model, max_tokens)
    if provider == "kimi":
        return _kimi_stream(system, messages, on_chunk, model, max_tokens)
    if provider == "glm":
        return _glm_stream(system, messages, on_chunk, model, max_tokens)
    if provider == "ollama":
        return _ollama_stream(system, messages, on_chunk, model, max_tokens)
    return _anthropic_stream(system, messages, on_chunk, model, max_tokens)


# ── API publique ──────────────────────────────────────────────────────────────

def _adapt(system: str, task: str | None, provider: str, model: str) -> str:
    """Prompt système adapté au moteur (core/engine_prompts) — POINT CENTRAL.
    Anthropic → identité (zéro régression). Jamais bloquant : en cas d'erreur
    du module d'adaptation, le system d'origine part tel quel."""
    try:
        from core.engine_prompts import adapt_system
        return adapt_system(system, task=task, provider=provider, model=model)
    except Exception:
        return system


def chat(system: str, messages: list, tier: str = "creative",
         max_tokens: int = 2048, task: str | None = None) -> str:
    """Conversation multi-tours : messages = [{"role": "user"|"assistant", "content": str}]."""
    provider, creative = _resolve_engine(task)
    model = _model(tier, provider, creative)
    return _dispatch_complete(provider, _adapt(system, task, provider, model),
                              messages, model, max_tokens)


def chat_stream(system: str, messages: list, on_chunk=None, tier: str = "creative",
                max_tokens: int = 2048, task: str | None = None) -> str:
    """Conversation multi-tours en streaming : on_chunk(str) à chaque fragment."""
    provider, creative = _resolve_engine(task)
    model = _model(tier, provider, creative)
    return _dispatch_stream(provider, _adapt(system, task, provider, model),
                            messages, on_chunk, model, max_tokens)


def complete(system: str, user: str, tier: str = "utility",
             max_tokens: int = 2048, task: str | None = None) -> str:
    """Appel one-shot : un message utilisateur → texte complet."""
    return chat(system, [{"role": "user", "content": user}], tier, max_tokens, task)


def stream(system: str, user: str, on_chunk=None, tier: str = "creative",
           max_tokens: int = 4096, task: str | None = None) -> str:
    """Appel en streaming : on_chunk(str) à chaque fragment ; renvoie le texte complet."""
    provider, creative = _resolve_engine(task)
    model = _model(tier, provider, creative)
    return _dispatch_stream(provider, _adapt(system, task, provider, model),
                            [{"role": "user", "content": user}],
                            on_chunk, model, max_tokens)
