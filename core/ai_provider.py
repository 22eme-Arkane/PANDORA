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
    "ollama_num_ctx"     : plafond de la fenêtre de contexte demandée à Ollama (défaut 32768)
    "local_preset"       : serveur OpenAI-compatible LOCAL : lmstudio | llamacpp | vllm | jan | other
    "local_url"          : son adresse (vide = celle du préréglage, voir core/local_llm)
    "local_model"        : identifiant du modèle chargé sur ce serveur
    "local_key"          : clé facultative (un serveur local n'en demande pas)
    "ai_task_engines"    : {task_key: engine_key} — moteur par tâche (override du défaut)

Moteurs (engine_key) — granularité du choix par tâche :
    "claude" · "fable5" · "gpt" · "mistral" · "kimi" · "glm" · "ollama" · "local" · "custom"

IA LOCALES « comme Claude » (24/09/2026, core/local_llm) : fenêtre de contexte
Ollama dimensionnée sur l'appel (sinon l'entrée était coupée en silence),
réflexion désactivée quand le modèle sait penser (comme `thinking: disabled`
chez Anthropic), blocs <think> retirés des réponses et des flux de TOUS les
moteurs non-Anthropic, garde vision, consommation journalisée pour tous.

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

_PROVIDERS = ("anthropic", "openai", "mistral", "kimi", "glm", "ollama", "local", "custom")
#: Fournisseurs qui tournent sur la machine : temps de réponse longs tolérés,
#: aucune clé, directives renforcées (core/engine_prompts).
_LOCAL_PROVIDERS = ("ollama", "local")
_LOCAL_TIMEOUT = (10, 1800)      # un gros modèle sur CPU met de longues minutes

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
    if provider == "local":
        return creative_model or (_cfg().get("local_model") or "").strip()
    if provider == "custom":
        return creative_model or (_cfg().get("custom_model") or "").strip()
    return creative_model or _DEFAULT_CREATIVE


def is_local_provider(task: str | None = None) -> bool:
    """Vrai si la tâche est servie par une IA qui tourne sur la machine (ou par
    un fournisseur OpenAI-compatible pointé vers localhost)."""
    provider, _ = _resolve_engine(task)
    if provider in _LOCAL_PROVIDERS:
        return True
    if provider in ("kimi", "glm", "custom"):
        url = (_cfg().get(f"{provider}_url") or "").lower()
        return "localhost" in url or "127.0.0.1" in url
    return False


# ── Nom d'affichage du moteur global ────────────────────────────────────────────

_NAME_CACHE: str | None = None


def ai_name() -> str:
    """Nom d'affichage du moteur GLOBAL — pour les libellés UI dynamiques.
    Mis en cache ; les Paramètres appellent refresh_name_cache() après sauvegarde."""
    global _NAME_CACHE
    if _NAME_CACHE is None:
        # Toujours le NOM PRÉCIS du moteur résolu (« Fable 5 », « Claude Opus 4.8 »,
        # « GPT-5.5 »…) : « Anthropic optimisé » / « ChatGPT optimisé » ne disent pas
        # quel modèle travaille réellement (demande Matthieu 2026-07-23).
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
    # Serveur LOCAL éteint : « Connection refused » brut n'aide personne.
    if ("connection refused" in low or "max retries exceeded" in low
            or "failed to establish" in low or "winerror 10061" in low
            or "actively refused" in low):
        return _tr("Serveur IA injoignable — lancez le serveur local (Ollama, LM Studio, "
                   "llama.cpp…) ou vérifiez son adresse dans Paramètres → Assistant IA, "
                   "puis relancez.")
    if "does not support images" in low or "ne voit pas les images" in low:
        return msg
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
    if provider == "local":
        from core.local_llm import preset, preset_key
        return creative_model or ("Serveur IA local · " + preset(preset_key(_cfg()))["name"])
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
    if provider == "local":
        # Adresse toujours connue (préréglage) ; seul le MODÈLE peut manquer.
        if not (cfg.get("local_model") or "").strip():
            return ("Aucun modèle choisi pour le serveur IA local — Paramètres → Assistant IA → "
                    "« Tester » liste les modèles chargés sur le serveur, choisissez-en un.")
        return None
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


# ── Journalisation du coût : quelle tâche est en cours, dans CE thread ───────
# Les adaptateurs bas niveau ne reçoivent pas le `task` (il faudrait changer la
# signature de _dispatch_complete, dont le harnais lit la source). On le dépose
# donc dans un contexte propre au thread : les workers PANDORA tournent chacun
# dans leur QThread, il n'y a donc aucun mélange possible entre deux tâches
# simultanées.
import threading as _threading

_task_ctx = _threading.local()


def _set_task_ctx(task: str | None, model: str, provider: str) -> None:
    _task_ctx.task = task or ""
    _task_ctx.model = model or ""
    _task_ctx.provider = provider or ""


def _note_usage(msg) -> None:
    """Range la consommation d'une réponse Anthropic dans « Coût du projet ».

    Silencieuse par construction : un journal indisponible ne doit jamais
    remonter dans un appel IA que l'utilisateur a déjà payé.
    """
    try:
        from core.ai_spend import note_message
        note_message(msg,
                     getattr(_task_ctx, "model", "") or "",
                     getattr(_task_ctx, "task", "") or "",
                     provider=getattr(_task_ctx, "provider", "") or "anthropic")
    except Exception:
        pass


def _note_counts(input_tokens, output_tokens) -> None:
    """Même journal, à partir de DÉCOMPTES (OpenAI-compatibles : `usage`,
    Ollama : prompt_eval_count / eval_count). Les moteurs locaux coûtent 0 $ :
    les jetons restent visibles dans « Coût du projet », le montant reste nul.
    Silencieuse par construction (voir _note_usage)."""
    try:
        from core.ai_spend import note_usage
        note_usage(getattr(_task_ctx, "model", "") or "",
                   getattr(_task_ctx, "task", "") or "",
                   int(input_tokens or 0), int(output_tokens or 0),
                   provider=getattr(_task_ctx, "provider", "") or "anthropic")
    except Exception:
        pass


def _note_oai_usage(j: dict) -> None:
    u = (j or {}).get("usage") or {}
    if u:
        _note_counts(u.get("prompt_tokens"), u.get("completion_tokens"))


def _note_ollama_usage(j: dict) -> None:
    if (j or {}).get("prompt_eval_count") or (j or {}).get("eval_count"):
        _note_counts(j.get("prompt_eval_count"), j.get("eval_count"))


def _anthropic_complete(system, messages, model, max_tokens) -> str:
    msg = _anthropic_client().messages.create(
        model=model, max_tokens=max_tokens, system=system, messages=messages,
        **_anthropic_extra(model),
    )
    _note_usage(msg)
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
        # Le décompte n'est disponible qu'une fois le flux terminé.
        try:
            _note_usage(st.get_final_message())
        except Exception:
            pass
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


# ── Adaptateur OpenAI-compatible UNIQUE ─────────────────────────────────────
# Un seul chemin d'appel pour OpenAI, Mistral, Kimi, GLM, le serveur local et
# le fournisseur personnalisé : seule la charge utile (URL, clé, options)
# diffère. Avant le 24/09/2026 chaque moteur avait sa copie du même code —
# et aucune copie ne retirait la pensée <think> ni ne journalisait les jetons.

def _oai_json(url: str, payload: dict, headers: dict, timeout=300) -> dict:
    import requests
    r = requests.post(url, json=payload, headers=headers, timeout=timeout)
    r.raise_for_status()
    j = r.json()
    _note_oai_usage(j)
    return j


def _oai_complete(url: str, payload: dict, headers: dict, timeout=300) -> str:
    from core.local_llm import strip_thinking
    j = _oai_json(url, payload, headers, timeout)
    return strip_thinking(j["choices"][0].get("message", {}).get("content", "") or "")


def _oai_stream(url: str, payload: dict, headers: dict, on_chunk, timeout=300) -> str:
    import json as _json
    import requests
    from core.local_llm import ThinkFilter
    filt = ThinkFilter()
    full = ""
    with requests.post(url, json=payload, headers=headers, timeout=timeout, stream=True) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line or not line.startswith(b"data:"):
                continue
            data = line[5:].strip()
            if data == b"[DONE]":
                break
            try:
                chunk = _json.loads(data)
            except Exception:
                continue
            if chunk.get("usage"):                      # stream_options.include_usage
                _note_oai_usage(chunk)
            try:
                # Les modèles « thinking » (Kimi, GLM, DeepSeek…) posent leur
                # réflexion dans 'reasoning_content' : ignorée volontairement.
                delta = chunk["choices"][0]["delta"].get("content", "") or ""
            except Exception:
                continue
            if delta:
                vis = filt.feed(delta)
                if vis:
                    full += vis
                    if on_chunk:
                        on_chunk(vis)
    rest = filt.flush()
    if rest:
        full += rest
        if on_chunk:
            on_chunk(rest)
    return full


def _openai_payload(system, messages, model, max_tokens, stream_flag) -> tuple:
    msgs = _openai_messages(system, messages)
    payload = {"model": model, "max_completion_tokens": max_tokens,
               "messages": msgs, "stream": stream_flag}
    if stream_flag:
        payload["stream_options"] = {"include_usage": True}
    return ("https://api.openai.com/v1/chat/completions", payload,
            {"Authorization": f"Bearer {_cfg().get('openai_key', '').strip()}",
             "Content-Type": "application/json"})


def _openai_complete(system, messages, model, max_tokens) -> str:
    return _oai_complete(*_openai_payload(system, messages, model, max_tokens, False))


def _openai_stream(system, messages, on_chunk, model, max_tokens) -> str:
    return _oai_stream(*_openai_payload(system, messages, model, max_tokens, True), on_chunk)


def _mistral_payload(system, messages, model, max_tokens, stream_flag) -> tuple:
    msgs = _openai_messages(system, messages)
    return ("https://api.mistral.ai/v1/chat/completions", {
        "model": model, "max_tokens": max_tokens,
        "messages": msgs, "stream": stream_flag,
    }, {"Authorization": f"Bearer {_cfg().get('mistral_key', '').strip()}",
        "Content-Type": "application/json"})


def _mistral_complete(system, messages, model, max_tokens) -> str:
    return _oai_complete(*_mistral_payload(system, messages, model, max_tokens, False))


def _mistral_stream(system, messages, on_chunk, model, max_tokens) -> str:
    return _oai_stream(*_mistral_payload(system, messages, model, max_tokens, True), on_chunk)


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
    return _oai_complete(*_kimi_payload(system, messages, model, max_tokens, False))


def _kimi_stream(system, messages, on_chunk, model, max_tokens) -> str:
    # Kimi K2.7 est un modèle « thinking » : l'adaptateur commun ne garde que
    # 'content' (la réflexion est dans 'reasoning_content', ignorée volontairement).
    return _oai_stream(*_kimi_payload(system, messages, model, max_tokens, True), on_chunk)


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
    # Même chemin OpenAI-compatible que Kimi : seul le payload (URL + clé glm_*) diffère.
    return _oai_complete(*_glm_payload(system, messages, model, max_tokens, False))


def _glm_stream(system, messages, on_chunk, model, max_tokens) -> str:
    return _oai_stream(*_glm_payload(system, messages, model, max_tokens, True), on_chunk)


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
    return _oai_complete(*_custom_payload(system, messages, model, max_tokens, False), _custom_timeout())


def _custom_stream(system, messages, on_chunk, model, max_tokens) -> str:
    return _oai_stream(*_custom_payload(system, messages, model, max_tokens, True), on_chunk, _custom_timeout())


def _custom_timeout():
    u = _custom_base_url().lower()
    return _LOCAL_TIMEOUT if ("localhost" in u or "127.0.0.1" in u) else 300


# ── Serveur OpenAI-compatible LOCAL (LM Studio, llama.cpp, vLLM, Jan…) ───────

def _local_base_url() -> str:
    from core.local_llm import local_base_url
    return local_base_url(_cfg())


def _local_payload(system, messages, model, max_tokens, stream_flag) -> tuple:
    """Charge utile OpenAI stricte ; les serveurs qui l'acceptent (llama.cpp,
    vLLM, Jan) reçoivent en plus `chat_template_kwargs.enable_thinking=false`
    — la réflexion des Qwen3-like coûte le budget de sortie, comme chez Ollama
    (think:false) et Anthropic (thinking:disabled)."""
    from core.local_llm import preset, preset_key
    cfg = _cfg()
    p = preset(preset_key(cfg))
    msgs = _openai_messages(system, messages)
    key = (cfg.get("local_key") or "").strip() or "local"
    payload = {"model": model, "max_tokens": max_tokens, "messages": msgs, "stream": stream_flag}
    if p["think_kwargs"]:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    if stream_flag and p["usage_stream"]:
        payload["stream_options"] = {"include_usage": True}
    return (f"{_local_base_url()}/chat/completions", payload,
            {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})


def _local_complete(system, messages, model, max_tokens) -> str:
    return _oai_complete(*_local_payload(system, messages, model, max_tokens, False), _LOCAL_TIMEOUT)


def _local_stream(system, messages, on_chunk, model, max_tokens) -> str:
    return _oai_stream(*_local_payload(system, messages, model, max_tokens, True), on_chunk, _LOCAL_TIMEOUT)


# ── Ollama ───────────────────────────────────────────────────────────────────

def _ollama_url() -> str:
    return ((_cfg().get("ollama_url") or "http://localhost:11434").strip().rstrip("/"))


_OLLAMA_INFO: dict[tuple, dict] = {}       # (url, modèle) → {"caps": [...], "ctx": int}
_OLLAMA_CTX_USED: dict[str, int] = {}      # modèle → dernière fenêtre demandée (collante)


def _ollama_info(model: str) -> dict:
    """Capacités (completion, vision, thinking…) et contexte natif d'un modèle,
    lus UNE fois chez Ollama (/api/show). {} si le serveur ne les publie pas."""
    key = (_ollama_url(), model)
    if key in _OLLAMA_INFO:
        return _OLLAMA_INFO[key]
    info: dict = {}
    try:
        import requests
        r = requests.post(f"{_ollama_url()}/api/show", json={"model": model}, timeout=20)
        if r.ok:
            j = r.json()
            caps = j.get("capabilities")
            info["caps"] = [str(c).lower() for c in caps] if isinstance(caps, list) else None
            mi = j.get("model_info") or {}
            ctx = [v for k, v in mi.items() if str(k).endswith(".context_length")]
            info["ctx"] = int(ctx[0]) if ctx and isinstance(ctx[0], (int, float)) else 0
    except Exception:
        pass
    _OLLAMA_INFO[key] = info
    return info


def _ollama_request(system, messages, model, max_tokens, stream_flag) -> dict:
    """La requête /api/chat « comme Claude » : fenêtre de contexte dimensionnée
    sur l'appel (et jamais réduite ensuite, pour ne pas recharger le modèle),
    réflexion coupée si le modèle sait penser, garde vision."""
    from core.local_llm import ollama_num_ctx, vision_error, OLLAMA_CTX_DEFAULT
    msgs = _ollama_messages(system, messages)
    info = _ollama_info(model)
    caps = info.get("caps")
    err = vision_error(model, caps, messages)
    if err:
        raise RuntimeError(err)
    try:
        ceiling = int(_cfg().get("ollama_num_ctx") or OLLAMA_CTX_DEFAULT)
    except (TypeError, ValueError):
        ceiling = OLLAMA_CTX_DEFAULT
    ctx = ollama_num_ctx(messages, max_tokens, system, info.get("ctx") or 0, ceiling)
    ctx = max(ctx, _OLLAMA_CTX_USED.get(model, 0))
    _OLLAMA_CTX_USED[model] = ctx
    req = {"model": model, "messages": msgs, "stream": stream_flag,
           "options": {"num_predict": max_tokens, "num_ctx": ctx}}
    if caps and "thinking" in caps:
        req["think"] = False
    return req


def _ollama_complete(system, messages, model, max_tokens) -> str:
    import requests
    from core.local_llm import strip_thinking
    r = requests.post(f"{_ollama_url()}/api/chat",
                      json=_ollama_request(system, messages, model, max_tokens, False),
                      timeout=_LOCAL_TIMEOUT)
    r.raise_for_status()
    j = r.json()
    _note_ollama_usage(j)
    return strip_thinking(j.get("message", {}).get("content", "") or "")


def _ollama_stream(system, messages, on_chunk, model, max_tokens) -> str:
    import json as _json
    import requests
    from core.local_llm import ThinkFilter
    filt = ThinkFilter()
    full = ""
    with requests.post(f"{_ollama_url()}/api/chat",
                       json=_ollama_request(system, messages, model, max_tokens, True),
                       timeout=_LOCAL_TIMEOUT, stream=True) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            try:
                chunk = _json.loads(line)
            except Exception:
                continue
            delta = chunk.get("message", {}).get("content", "") or ""
            if delta:
                vis = filt.feed(delta)
                if vis:
                    full += vis
                    if on_chunk:
                        on_chunk(vis)
            if chunk.get("done"):
                _note_ollama_usage(chunk)
                break
    rest = filt.flush()
    if rest:
        full += rest
        if on_chunk:
            on_chunk(rest)
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
    if provider == "local":
        return _local_complete(system, messages, model, max_tokens)
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
    if provider == "local":
        return _local_stream(system, messages, on_chunk, model, max_tokens)
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
    _set_task_ctx(task, model, provider)
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
    _set_task_ctx(task, model, provider)
    if provider in ("openai", "mistral", "kimi", "glm", "local", "custom"):
        from core.local_llm import strip_thinking
        builder = {"openai": _openai_payload, "mistral": _mistral_payload,
                   "kimi": _kimi_payload, "glm": _glm_payload,
                   "local": _local_payload, "custom": _custom_payload}[provider]
        timeout = {"local": _LOCAL_TIMEOUT, "custom": _custom_timeout()}.get(provider, 300)
        j = _oai_json(*builder(sysp, messages, model, max_tokens, False), timeout)
        choice = j["choices"][0]
        return {"text": strip_thinking(choice.get("message", {}).get("content", "") or ""),
                "truncated": choice.get("finish_reason") == "length"}
    if provider == "ollama":
        import requests
        from core.local_llm import strip_thinking
        r = requests.post(f"{_ollama_url()}/api/chat",
                          json=_ollama_request(sysp, messages, model, max_tokens, False),
                          timeout=_LOCAL_TIMEOUT)
        r.raise_for_status()
        j = r.json()
        _note_ollama_usage(j)
        return {"text": strip_thinking(j.get("message", {}).get("content", "") or ""),
                "truncated": j.get("done_reason", "") == "length"}
    # Anthropic (défaut)
    msg = _anthropic_client().messages.create(
        model=model, max_tokens=max_tokens, system=sysp, messages=messages,
        **_anthropic_extra(model))
    _note_usage(msg)
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    return {"text": text, "truncated": getattr(msg, "stop_reason", "") == "max_tokens"}


# Relance de continuation : reprendre au caractère exact, sans répétition ni méta.
CONTINUE_PROMPT = ("Continue EXACTEMENT là où tu t'es arrêté, sans rien répéter ni "
                   "reformuler, sans préambule ni commentaire : reprends au caractère "
                   "suivant de ta réponse précédente.")


def chat_until_complete_ex(system: str, messages: list, tier: str = "creative",
                           max_tokens: int = 2048, task: str | None = None,
                           max_rounds: int = 4) -> dict:
    """chat() ANTI-TRONCATURE, avec REDDITION DE COMPTES.

    Si la réponse est coupée par la limite de longueur, demande automatiquement LA
    SUITE (le déjà-reçu repart comme message assistant + CONTINUE_PROMPT) et
    recolle, jusqu'à une fin normale (max `max_rounds` continuations). Longueur de
    sortie effective : (max_rounds+1) × max_tokens.

    Renvoie {"text", "truncated", "rounds"} : `truncated` reste VRAI si le texte
    est ENCORE coupé après la dernière continuation. L'appelant doit alors refuser
    d'enregistrer — un document tronqué enregistré en silence est une perte de
    données invisible (découpage arrêté au plan 28 sur la moitié d'un scénario,
    constat Matthieu 2026-07-25)."""
    full = ""
    msgs = list(messages)
    truncated = False
    rounds = 0
    for _ in range(max_rounds + 1):
        res = chat_ex(system, msgs, tier, max_tokens, task)
        full += res.get("text", "")
        truncated = bool(res.get("truncated"))
        if not truncated or not full:
            break
        rounds += 1
        msgs = list(messages) + [{"role": "assistant", "content": full},
                                 {"role": "user",      "content": CONTINUE_PROMPT}]
    return {"text": full, "truncated": truncated, "rounds": rounds}


def chat_until_complete(system: str, messages: list, tier: str = "creative",
                        max_tokens: int = 2048, task: str | None = None,
                        max_rounds: int = 4) -> str:
    """Idem, mais ne renvoie que le texte (appelants historiques)."""
    return chat_until_complete_ex(system, messages, tier, max_tokens,
                                  task, max_rounds).get("text", "")


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
    _set_task_ctx(task, model, provider)
    return _dispatch_stream(provider, _adapt(system, task, provider, model),
                            [{"role": "user", "content": user}],
                            on_chunk, model, max_tokens)
