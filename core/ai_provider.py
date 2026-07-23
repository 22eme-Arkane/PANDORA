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


from core.ai_registry import (ENGINE_ORDER, ENGINES as _REGISTRY_ENGINES,
                              PANDORA_OPTIMIZED, TASK_DEFAULTS, TASKS,
                              engine as _registry_engine,
                              profile_from_config as _profile_from_config,
                              recommended_engine_name,
                              resolve_engine as _registry_resolve)

# Forme historique conservée pour les pages et harnais existants.
ENGINES: dict[str, dict] = {
    key: {**item, "creative_model": item.get("model", "")}
    for key, item in _REGISTRY_ENGINES.items()
}

_PROVIDERS = ("anthropic", "openai", "mistral", "kimi", "glm", "ollama", "custom")

# Modèle par défaut (créatif) — Opus 4.8.
_DEFAULT_CREATIVE = "claude-opus-4-8"

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
    item = _registry_resolve(_cfg(), task)
    return item["provider"], item.get("model", "")


def _model(tier: str, provider: str | None = None, creative_model: str = "") -> str:
    # provider=None → moteur global (rétro-compatible avec les anciens appels)
    if provider is None:
        provider, creative_model = _resolve_engine()
    if provider == "anthropic":
        return (creative_model or _DEFAULT_CREATIVE) if tier == "creative" else _ANTHROPIC_UTILITY
    if provider == "openai":
        return (creative_model or (_cfg().get("openai_model") or "").strip()
                or _OPENAI_MODELS["creative" if tier == "creative" else "utility"])
    if provider == "mistral":
        if creative_model and creative_model not in ("mistral-large-latest",):
            return creative_model
        return _MISTRAL_MODELS["creative" if tier == "creative" else "utility"]
    if provider == "kimi":
        return creative_model or (_cfg().get("kimi_model") or "").strip() or _KIMI_DEFAULT_MODEL
    if provider == "glm":
        return creative_model or (_cfg().get("glm_model") or "").strip() or _GLM_DEFAULT_MODEL
    if provider == "ollama":
        return creative_model or (_cfg().get("ollama_model") or "llama3.1").strip() or "llama3.1"
    if provider == "custom":
        return creative_model or (_cfg().get("custom_model") or "").strip()
    return creative_model or _DEFAULT_CREATIVE


# ── Nom d'affichage du moteur global ────────────────────────────────────────────

_NAME_CACHE: str | None = None


def ai_name() -> str:
    """Nom d'affichage du moteur GLOBAL — pour les libellés UI dynamiques.
    Mis en cache ; les Paramètres appellent refresh_name_cache() après sauvegarde."""
    global _NAME_CACHE
    if _NAME_CACHE is None:
        cfg = _cfg()
        profile = _profile_from_config(cfg)
        if profile == "anthropic_optimized":
            _NAME_CACHE = "Anthropic optimisé"
        elif profile == "openai_optimized":
            _NAME_CACHE = "ChatGPT optimisé"
        else:
            _NAME_CACHE = _engine_display_name(*_resolve_engine())
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
    openai_quota = (
        "insufficient_quota" in low
        or "exceeded your current quota" in low
        or "you exceeded your quota" in low
        or "billing_hard_limit_reached" in low
        or "billing_not_active" in low
        or ("quota" in low and ("billing" in low or "plan" in low))
    )
    if openai_quota:
        return _tr("Crédits OpenAI épuisés ou plafond de dépenses atteint — "
                   "recharge les crédits ou vérifie les limites du projet OpenAI, "
                   "puis relance.")
    if ("credit balance" in low or "insufficient credit" in low
            or ("billing" in low and "credit" in low)):
        return _tr("Crédits API épuisés — recharge le compte du fournisseur "
                   "sélectionné puis relance. "
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
        return creative_model or "OpenAI"
    if provider == "mistral":
        return ENGINES["mistral"]["name"]
    if provider == "kimi":
        return ENGINES["kimi"]["name"]
    if provider == "glm":
        return ENGINES["glm"]["name"]
    if provider == "ollama":
        return creative_model or ENGINES["ollama"]["name"]
    if provider == "custom":
        return creative_model or "Fournisseur personnalisé"
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
            return "Clé OpenAI manquante — renseignez-la dans Paramètres."
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
    if provider == "custom":
        url = (cfg.get("custom_url") or "").strip().lower()
        if not url:
            return "URL du fournisseur personnalisé manquante — renseignez-la dans Paramètres."
        is_local = ("localhost" in url) or ("127.0.0.1" in url)
        if not is_local and not cfg.get("custom_key", "").strip():
            return "Clé du fournisseur personnalisé manquante — renseignez-la dans Paramètres."
        if not (cfg.get("custom_model") or "").strip():
            return "Modèle personnalisé manquant — renseignez-le dans Paramètres."
        return None
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


def _openai_content(content):
    """Anthropic blocks → Chat Completions multimodal blocks."""
    if isinstance(content, str):
        return content
    out = []
    for block in content or []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            out.append({"type": "text", "text": block.get("text", "")})
        elif block.get("type") == "image":
            src = block.get("source") or {}
            if src.get("type") == "base64" and src.get("data"):
                mime = src.get("media_type") or "image/jpeg"
                out.append({"type": "image_url", "image_url": {
                    "url": f"data:{mime};base64,{src['data']}", "detail": "high"}})
        elif block.get("type") == "image_url":
            out.append(block)
    return out or ""


def _openai_messages(system, messages) -> list:
    out = [{"role": "system", "content": system}] if system else []
    out += [{"role": m["role"], "content": _openai_content(m.get("content", ""))}
            for m in messages]
    return out


def _ollama_messages(system, messages) -> list:
    """Convertit les blocs image en champ ``images`` attendu par Ollama."""
    out = [{"role": "system", "content": system}] if system else []
    for message in messages:
        content = message.get("content", "")
        if isinstance(content, str):
            out.append({"role": message["role"], "content": content})
            continue
        texts, images = [], []
        for block in content or []:
            if block.get("type") == "text":
                texts.append(block.get("text", ""))
            elif block.get("type") == "image":
                src = block.get("source") or {}
                if src.get("data"):
                    images.append(src["data"])
        item = {"role": message["role"], "content": "\n".join(texts)}
        if images:
            item["images"] = images
        out.append(item)
    return out


def _openai_payload(system, messages, model, max_tokens, stream_flag) -> tuple:
    msgs = _openai_messages(system, messages)
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
    msgs = _openai_messages(system, messages)
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
    msgs = _openai_messages(system, messages)
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
    msgs = _openai_messages(system, messages)
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


def _custom_base_url() -> str:
    return ((_cfg().get("custom_url") or "").strip().rstrip("/"))


def _custom_payload(system, messages, model, max_tokens, stream_flag) -> tuple:
    """Fournisseur personnalisé au format OpenAI-compatible."""
    msgs = _openai_messages(system, messages)
    key = _cfg().get("custom_key", "").strip() or "local"
    return (f"{_custom_base_url()}/chat/completions", {
        "model": model, "max_tokens": max_tokens,
        "messages": msgs, "stream": stream_flag,
    }, {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})


def _custom_complete(system, messages, model, max_tokens) -> str:
    import requests
    url, payload, headers = _custom_payload(system, messages, model, max_tokens, False)
    r = requests.post(url, json=payload, headers=headers, timeout=300)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _custom_stream(system, messages, on_chunk, model, max_tokens) -> str:
    import json as _json
    import requests
    url, payload, headers = _custom_payload(system, messages, model, max_tokens, True)
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


def _ollama_url() -> str:
    return ((_cfg().get("ollama_url") or "http://localhost:11434").strip().rstrip("/"))


def _ollama_complete(system, messages, model, max_tokens) -> str:
    import requests
    msgs = _ollama_messages(system, messages)
    r = requests.post(f"{_ollama_url()}/api/chat", json={
        "model": model, "messages": msgs, "stream": False,
        "options": {"num_predict": max_tokens},
    }, timeout=600)
    r.raise_for_status()
    return r.json().get("message", {}).get("content", "")


def _ollama_stream(system, messages, on_chunk, model, max_tokens) -> str:
    import json as _json
    import requests
    msgs = _ollama_messages(system, messages)
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
    if provider == "custom":
        return _custom_complete(system, messages, model, max_tokens)
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
    if provider == "custom":
        return _custom_stream(system, messages, on_chunk, model, max_tokens)
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


def chat_ex(system: str, messages: list, tier: str = "creative",
            max_tokens: int = 2048, task: str | None = None) -> dict:
    """Comme chat(), mais renvoie {"text": str, "truncated": bool} : la coupe par
    LIMITE DE LONGUEUR est détectée précisément (stop_reason « max_tokens » chez
    Anthropic, finish_reason « length » chez les OpenAI-compatibles, done_reason
    chez Ollama) — le socle des boucles de continuation anti-troncature
    (co-écriture : fins de scénario perdues, constat Matthieu 2026-07-21)."""
    provider, creative = _resolve_engine(task)
    model = _model(tier, provider, creative)
    sysp  = _adapt(system, task, provider, model)
    if provider in ("openai", "mistral", "kimi", "glm", "custom"):
        import requests
        builder = {"openai": _openai_payload, "mistral": _mistral_payload,
                   "kimi": _kimi_payload, "glm": _glm_payload,
                   "custom": _custom_payload}[provider]
        url, payload, headers = builder(sysp, messages, model, max_tokens, False)
        r = requests.post(url, json=payload, headers=headers, timeout=300)
        r.raise_for_status()
        choice = r.json()["choices"][0]
        return {"text": choice.get("message", {}).get("content", "") or "",
                "truncated": choice.get("finish_reason") == "length"}
    if provider == "ollama":
        import requests
        msgs = _ollama_messages(sysp, messages)
        r = requests.post(f"{_ollama_url()}/api/chat", json={
            "model": model, "messages": msgs, "stream": False,
            "options": {"num_predict": max_tokens}}, timeout=600)
        r.raise_for_status()
        j = r.json()
        return {"text": j.get("message", {}).get("content", "") or "",
                "truncated": j.get("done_reason", "") == "length"}
    # Anthropic (défaut)
    msg = _anthropic_client().messages.create(
        model=model, max_tokens=max_tokens, system=sysp, messages=messages,
        **_anthropic_extra(model))
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    return {"text": text, "truncated": getattr(msg, "stop_reason", "") == "max_tokens"}


# Relance de continuation : reprendre au caractère exact, sans répétition ni méta.
CONTINUE_PROMPT = ("Continue EXACTEMENT là où tu t'es arrêté, sans rien répéter ni "
                   "reformuler, sans préambule ni commentaire : reprends au caractère "
                   "suivant de ta réponse précédente.")


def chat_until_complete(system: str, messages: list, tier: str = "creative",
                        max_tokens: int = 2048, task: str | None = None,
                        max_rounds: int = 4) -> str:
    """chat() ANTI-TRONCATURE : si la réponse est coupée par la limite de longueur,
    demande automatiquement LA SUITE (le déjà-reçu repart comme message assistant +
    CONTINUE_PROMPT) et recolle, jusqu'à une fin normale (max `max_rounds`
    continuations). Longueur de sortie effective : (max_rounds+1) × max_tokens —
    plus aucune fin de scénario perdue en co-écriture."""
    full = ""
    msgs = list(messages)
    for _ in range(max_rounds + 1):
        res = chat_ex(system, msgs, tier, max_tokens, task)
        full += res.get("text", "")
        if not res.get("truncated") or not full:
            break
        msgs = list(messages) + [{"role": "assistant", "content": full},
                                 {"role": "user",      "content": CONTINUE_PROMPT}]
    return full


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
