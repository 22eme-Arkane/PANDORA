"""
core/ai_provider.py — Couche d'abstraction des assistants IA texte (Cinéma + Live).

Tous les appels IA TEXTE de PANDORA passent par ce module : le fournisseur et le
modèle se choisissent dans Paramètres (config.json). Les appels VISION (analyse
d'images : références visuelles, portraits Nano Banana, style ref) restent sur
Anthropic — les autres fournisseurs gèrent la vision différemment (hors périmètre v1).

Config (config.json) :
    "ai_provider"        : "anthropic" (défaut) | "openai" | "mistral" | "ollama"
    "ai_model_creative"  : modèle du tier créatif Anthropic (défaut "claude-sonnet-4-6" ;
                           "claude-fable-5" pour Fable 5)
    "anthropic_key"      : clé API Anthropic (Claude / Fable 5)
    "openai_key"         : clé API OpenAI (GPT-5.5)
    "openai_model"       : modèle OpenAI (défaut "gpt-5.5")
    "mistral_key"        : clé API Mistral
    "ollama_url"         : URL du serveur Ollama (défaut http://localhost:11434)
    "ollama_model"       : modèle Ollama (défaut "llama3.1")
    "ai_task_engines"    : {task_key: engine_key} — moteur par tâche (override du défaut)

Moteurs (engine_key) — granularité du choix par tâche :
    "claude" · "fable5" · "gpt" · "mistral" · "ollama"

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

_PROVIDERS = ("anthropic", "openai", "mistral", "ollama")

# Moteur = (fournisseur, modèle créatif, nom d'affichage). Permet de choisir
# Claude vs Fable 5 (même fournisseur Anthropic, modèles différents) par tâche.
ENGINES: dict[str, dict] = {
    "claude":  {"provider": "anthropic", "creative_model": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6"},
    "opus":    {"provider": "anthropic", "creative_model": "claude-opus-4-8",   "name": "Claude Opus 4.8"},
    "haiku":   {"provider": "anthropic", "creative_model": "claude-haiku-4-5",  "name": "Claude Haiku 4.5"},
    "fable5":  {"provider": "anthropic", "creative_model": "claude-fable-5",    "name": "Fable 5"},
    "gpt":     {"provider": "openai",    "creative_model": "",                  "name": "GPT-5.5"},
    "mistral": {"provider": "mistral",   "creative_model": "",                  "name": "Mistral"},
    "ollama":  {"provider": "ollama",    "creative_model": "",                  "name": "Ollama"},
}

# Ordre d'affichage des moteurs dans les menus (Paramètres avancés).
ENGINE_ORDER = ["claude", "opus", "haiku", "fable5", "gpt", "mistral", "ollama"]

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
]

_ANTHROPIC_UTILITY = "claude-haiku-4-5"
_MISTRAL_MODELS = {"utility": "mistral-small-latest", "creative": "mistral-large-latest"}
_OPENAI_MODELS  = {"utility": "gpt-5.5", "creative": "gpt-5.5"}


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
    return m or "claude-sonnet-4-6"


def _resolve_engine(task: str | None = None) -> tuple[str, str]:
    """Renvoie (provider, creative_model) pour une tâche — override si défini,
    sinon le moteur global. Ne dégrade jamais le comportement par défaut."""
    cfg = _cfg()
    if task:
        eng_key = (cfg.get("ai_task_engines") or {}).get(task)
        if eng_key and eng_key in ENGINES:
            e = ENGINES[eng_key]
            return e["provider"], e["creative_model"]
    provider = (cfg.get("ai_provider") or "anthropic").strip().lower()
    if provider not in _PROVIDERS:
        provider = "anthropic"
    creative = (cfg.get("ai_model_creative") or "").strip() or "claude-sonnet-4-6"
    return provider, creative


def _model(tier: str, provider: str | None = None, creative_model: str = "") -> str:
    # provider=None → moteur global (rétro-compatible avec les anciens appels)
    if provider is None:
        provider, creative_model = _resolve_engine()
    if provider == "anthropic":
        return (creative_model or "claude-sonnet-4-6") if tier == "creative" else _ANTHROPIC_UTILITY
    if provider == "openai":
        m = (_cfg().get("openai_model") or "").strip()
        return m or _OPENAI_MODELS["creative" if tier == "creative" else "utility"]
    if provider == "mistral":
        return _MISTRAL_MODELS["creative" if tier == "creative" else "utility"]
    if provider == "ollama":
        return (_cfg().get("ollama_model") or "llama3.1").strip() or "llama3.1"
    return creative_model or "claude-sonnet-4-6"


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
            _NAME_CACHE = {"mistral": "Mistral", "ollama": "Ollama"}.get(
                provider, provider.capitalize())
    return _NAME_CACHE


def refresh_name_cache() -> None:
    global _NAME_CACHE
    _NAME_CACHE = None


def brand(text: str) -> str:
    """Remplace « Claude » par le nom du moteur global dans un libellé UI.
    À appliquer APRÈS translate()."""
    n = ai_name()
    return text if n == "Claude" else text.replace("Claude", n)


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
    if provider == "ollama":
        return None   # serveur local, pas de clé ; l'erreur réseau parlera d'elle-même
    return None


# ── Adaptateurs (reçoivent le MODÈLE résolu, donc indépendants du global) ────────

def _anthropic_client():
    import anthropic
    return anthropic.Anthropic(api_key=_cfg().get("anthropic_key", "").strip())


def _anthropic_complete(system, messages, model, max_tokens) -> str:
    msg = _anthropic_client().messages.create(
        model=model, max_tokens=max_tokens, system=system, messages=messages,
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def _anthropic_stream(system, messages, on_chunk, model, max_tokens) -> str:
    full = ""
    with _anthropic_client().messages.stream(
        model=model, max_tokens=max_tokens, system=system, messages=messages,
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
    if provider == "ollama":
        return _ollama_complete(system, messages, model, max_tokens)
    return _anthropic_complete(system, messages, model, max_tokens)


def _dispatch_stream(provider, system, messages, on_chunk, model, max_tokens) -> str:
    if provider == "openai":
        return _openai_stream(system, messages, on_chunk, model, max_tokens)
    if provider == "mistral":
        return _mistral_stream(system, messages, on_chunk, model, max_tokens)
    if provider == "ollama":
        return _ollama_stream(system, messages, on_chunk, model, max_tokens)
    return _anthropic_stream(system, messages, on_chunk, model, max_tokens)


# ── API publique ──────────────────────────────────────────────────────────────

def chat(system: str, messages: list, tier: str = "creative",
         max_tokens: int = 2048, task: str | None = None) -> str:
    """Conversation multi-tours : messages = [{"role": "user"|"assistant", "content": str}]."""
    provider, creative = _resolve_engine(task)
    return _dispatch_complete(provider, system, messages,
                              _model(tier, provider, creative), max_tokens)


def chat_stream(system: str, messages: list, on_chunk=None, tier: str = "creative",
                max_tokens: int = 2048, task: str | None = None) -> str:
    """Conversation multi-tours en streaming : on_chunk(str) à chaque fragment."""
    provider, creative = _resolve_engine(task)
    return _dispatch_stream(provider, system, messages, on_chunk,
                            _model(tier, provider, creative), max_tokens)


def complete(system: str, user: str, tier: str = "utility",
             max_tokens: int = 2048, task: str | None = None) -> str:
    """Appel one-shot : un message utilisateur → texte complet."""
    return chat(system, [{"role": "user", "content": user}], tier, max_tokens, task)


def stream(system: str, user: str, on_chunk=None, tier: str = "creative",
           max_tokens: int = 4096, task: str | None = None) -> str:
    """Appel en streaming : on_chunk(str) à chaque fragment ; renvoie le texte complet."""
    provider, creative = _resolve_engine(task)
    return _dispatch_stream(provider, system, [{"role": "user", "content": user}],
                            on_chunk, _model(tier, provider, creative), max_tokens)
