"""
core/ai_provider.py — Couche d'abstraction des assistants IA texte (Cinéma + Live).

Tous les appels IA TEXTE de PANDORA passent par ce module : le fournisseur et le
modèle se choisissent dans Paramètres (config.json). Les appels VISION (analyse
d'images : références visuelles, portraits Nano Banana, style ref) restent sur
Anthropic — les autres fournisseurs gèrent la vision différemment (hors périmètre v1).

Config (config.json) :
    "ai_provider"        : "anthropic" (défaut) | "mistral" | "ollama"
    "ai_model_creative"  : modèle du tier créatif (défaut "claude-sonnet-4-6" ;
                           "claude-fable-5" pour Fable 5)
    "mistral_key"        : clé API Mistral (si provider mistral)
    "ollama_url"         : URL du serveur Ollama (défaut http://localhost:11434)
    "ollama_model"       : modèle Ollama (défaut "llama3.1")

Tiers de modèles :
    "utility"  — tâches rapides / peu chères : traduction, extractions JSON courtes
    "creative" — tâches longues / créatives : storyboard, arrangement, mise en page

API :
    complete(system, user, tier="utility", max_tokens=2048) -> str
    stream(system, user, on_chunk, tier="creative", max_tokens=4096) -> str
    chat(system, messages, tier="creative", max_tokens=2048) -> str
    key_error() -> str | None     # message d'erreur si la clé du fournisseur manque
    ai_name() -> str              # nom d'affichage : "Claude", "Fable 5", "Mistral"…
"""

from __future__ import annotations


# ── Config ────────────────────────────────────────────────────────────────────

def _cfg() -> dict:
    from core.config import load_config
    return load_config()


def get_provider() -> str:
    p = (_cfg().get("ai_provider") or "anthropic").strip().lower()
    return p if p in ("anthropic", "mistral", "ollama") else "anthropic"


def get_creative_model() -> str:
    """Modèle du tier créatif chez Anthropic (Sonnet par défaut, Fable 5 en option)."""
    m = (_cfg().get("ai_model_creative") or "").strip()
    return m or "claude-sonnet-4-6"


_ANTHROPIC_UTILITY = "claude-haiku-4-5"

# Tiers des autres fournisseurs (ajustables)
_MISTRAL_MODELS = {"utility": "mistral-small-latest", "creative": "mistral-large-latest"}


def _model(tier: str) -> str:
    provider = get_provider()
    if provider == "anthropic":
        return get_creative_model() if tier == "creative" else _ANTHROPIC_UTILITY
    if provider == "mistral":
        return _MISTRAL_MODELS["creative" if tier == "creative" else "utility"]
    if provider == "ollama":
        return (_cfg().get("ollama_model") or "llama3.1").strip() or "llama3.1"
    return get_creative_model()


_NAME_CACHE: str | None = None


def ai_name() -> str:
    """Nom d'affichage de l'assistant actif — pour les libellés UI dynamiques.
    Mis en cache (translate() l'appelle pour chaque libellé) ; les Paramètres
    appellent refresh_name_cache() après sauvegarde."""
    global _NAME_CACHE
    if _NAME_CACHE is None:
        provider = get_provider()
        if provider == "anthropic":
            _NAME_CACHE = "Fable 5" if "fable" in get_creative_model() else "Claude"
        else:
            _NAME_CACHE = {"mistral": "Mistral", "ollama": "Ollama"}.get(
                provider, provider.capitalize())
    return _NAME_CACHE


def refresh_name_cache() -> None:
    global _NAME_CACHE
    _NAME_CACHE = None


def brand(text: str) -> str:
    """Remplace « Claude » par le nom de l'assistant actif dans un libellé UI.

    À appliquer APRÈS translate() : `brand(translate("Analyser avec Claude"))` —
    fonctionne ainsi en FR comme en EN, et ne change rien quand l'assistant est Claude.
    """
    n = ai_name()
    return text if n == "Claude" else text.replace("Claude", n)


def key_error() -> str | None:
    """Message d'erreur si la clé/connexion du fournisseur actif manque, sinon None."""
    provider = get_provider()
    cfg = _cfg()
    if provider == "anthropic":
        if not cfg.get("anthropic_key", "").strip():
            return ("Clé Anthropic (Claude) manquante — renseignez-la dans Paramètres.")
        return None
    if provider == "mistral":
        if not cfg.get("mistral_key", "").strip():
            return "Clé Mistral manquante — renseignez-la dans Paramètres."
        return None
    if provider == "ollama":
        return None   # serveur local, pas de clé ; l'erreur réseau parlera d'elle-même
    return None


# ── Adaptateurs ───────────────────────────────────────────────────────────────

def _anthropic_client():
    import anthropic
    return anthropic.Anthropic(api_key=_cfg().get("anthropic_key", "").strip())


def _anthropic_complete(system, messages, tier, max_tokens) -> str:
    msg = _anthropic_client().messages.create(
        model=_model(tier), max_tokens=max_tokens, system=system, messages=messages,
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def _anthropic_stream(system, messages, on_chunk, tier, max_tokens) -> str:
    full = ""
    with _anthropic_client().messages.stream(
        model=_model(tier), max_tokens=max_tokens, system=system, messages=messages,
    ) as st:
        for t in st.text_stream:
            full += t
            if on_chunk:
                on_chunk(t)
    return full


def _mistral_payload(system, messages, tier, max_tokens, stream_flag) -> tuple:
    msgs = [{"role": "system", "content": system}] if system else []
    msgs += [{"role": m["role"], "content": m["content"]} for m in messages]
    return ("https://api.mistral.ai/v1/chat/completions", {
        "model": _model(tier), "max_tokens": max_tokens,
        "messages": msgs, "stream": stream_flag,
    }, {"Authorization": f"Bearer {_cfg().get('mistral_key', '').strip()}",
        "Content-Type": "application/json"})


def _mistral_complete(system, messages, tier, max_tokens) -> str:
    import requests
    url, payload, headers = _mistral_payload(system, messages, tier, max_tokens, False)
    r = requests.post(url, json=payload, headers=headers, timeout=300)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _mistral_stream(system, messages, on_chunk, tier, max_tokens) -> str:
    import json as _json
    import requests
    url, payload, headers = _mistral_payload(system, messages, tier, max_tokens, True)
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


def _ollama_complete(system, messages, tier, max_tokens) -> str:
    import requests
    msgs = ([{"role": "system", "content": system}] if system else []) + list(messages)
    r = requests.post(f"{_ollama_url()}/api/chat", json={
        "model": _model(tier), "messages": msgs, "stream": False,
        "options": {"num_predict": max_tokens},
    }, timeout=600)
    r.raise_for_status()
    return r.json().get("message", {}).get("content", "")


def _ollama_stream(system, messages, on_chunk, tier, max_tokens) -> str:
    import json as _json
    import requests
    msgs = ([{"role": "system", "content": system}] if system else []) + list(messages)
    full = ""
    with requests.post(f"{_ollama_url()}/api/chat", json={
        "model": _model(tier), "messages": msgs, "stream": True,
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


# ── API publique ──────────────────────────────────────────────────────────────

def chat(system: str, messages: list, tier: str = "creative",
         max_tokens: int = 2048) -> str:
    """Conversation multi-tours : messages = [{"role": "user"|"assistant", "content": str}]."""
    provider = get_provider()
    if provider == "mistral":
        return _mistral_complete(system, messages, tier, max_tokens)
    if provider == "ollama":
        return _ollama_complete(system, messages, tier, max_tokens)
    return _anthropic_complete(system, messages, tier, max_tokens)


def chat_stream(system: str, messages: list, on_chunk=None, tier: str = "creative",
                max_tokens: int = 2048) -> str:
    """Conversation multi-tours en streaming : on_chunk(str) à chaque fragment."""
    provider = get_provider()
    if provider == "mistral":
        return _mistral_stream(system, messages, on_chunk, tier, max_tokens)
    if provider == "ollama":
        return _ollama_stream(system, messages, on_chunk, tier, max_tokens)
    return _anthropic_stream(system, messages, on_chunk, tier, max_tokens)


def complete(system: str, user: str, tier: str = "utility",
             max_tokens: int = 2048) -> str:
    """Appel one-shot : un message utilisateur → texte complet."""
    return chat(system, [{"role": "user", "content": user}], tier, max_tokens)


def stream(system: str, user: str, on_chunk=None, tier: str = "creative",
           max_tokens: int = 4096) -> str:
    """Appel en streaming : on_chunk(str) à chaque fragment ; renvoie le texte complet."""
    provider = get_provider()
    messages = [{"role": "user", "content": user}]
    if provider == "mistral":
        return _mistral_stream(system, messages, on_chunk, tier, max_tokens)
    if provider == "ollama":
        return _ollama_stream(system, messages, on_chunk, tier, max_tokens)
    return _anthropic_stream(system, messages, on_chunk, tier, max_tokens)
