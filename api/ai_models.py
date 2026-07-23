"""Découverte non bloquante des modèles réellement accessibles aux clés PANDORA.

Les fonctions réseau sont appelées par :class:`ModelDiscoveryWorker`, jamais depuis
le thread UI. Un échec chez un fournisseur n'efface pas les résultats des autres.
"""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal


_DEFAULT_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "mistral": "https://api.mistral.ai/v1",
    "kimi": "https://api.moonshot.ai/v1",
    "glm": "https://open.bigmodel.cn/api/paas/v4",
    "ollama": "http://localhost:11434",
}


def _local(url: str) -> bool:
    low = (url or "").lower()
    return "localhost" in low or "127.0.0.1" in low


def _compatible(provider: str, model_id: str) -> bool:
    """Écarte les modèles manifestement incompatibles avec les tâches de texte."""
    mid = (model_id or "").lower()
    if not mid:
        return False
    if provider == "anthropic":
        return mid.startswith("claude-")
    if provider == "openai":
        excluded = ("image", "audio", "realtime", "transcribe", "tts", "whisper",
                    "embedding", "moderation", "sora", "search", "computer-use")
        if any(x in mid for x in excluded):
            return False
        return mid.startswith(("gpt-", "o1", "o3", "o4", "chat-latest"))
    return True


def _openai_compatible_models(provider: str, base: str, key: str,
                              timeout: int = 20) -> list[str]:
    import requests
    headers = {"Authorization": f"Bearer {key or 'local'}"}
    r = requests.get(f"{base.rstrip('/')}/models", headers=headers, timeout=timeout)
    r.raise_for_status()
    data = r.json().get("data", [])
    out = []
    for item in data:
        if isinstance(item, dict):
            mid = str(item.get("id") or "").strip()
            caps = item.get("capabilities") or {}
            if caps and caps.get("completion_chat") is False:
                continue
        else:
            mid = str(item).strip()
        if _compatible(provider, mid):
            out.append(mid)
    return sorted(set(out), key=str.lower)


def discover_provider(provider: str, cfg: dict, timeout: int = 20) -> list[str]:
    provider = (provider or "").strip().lower()
    if provider == "ollama":
        import requests
        base = (cfg.get("ollama_url") or _DEFAULT_URLS["ollama"]).strip().rstrip("/")
        r = requests.get(f"{base}/api/tags", timeout=timeout)
        r.raise_for_status()
        return sorted({str(x.get("model") or x.get("name") or "").strip()
                       for x in r.json().get("models", [])
                       if x.get("model") or x.get("name")}, key=str.lower)
    if provider == "anthropic":
        import requests
        key = (cfg.get("anthropic_key") or "").strip()
        if not key:
            return []
        r = requests.get(f"{_DEFAULT_URLS['anthropic']}/models", headers={
            "x-api-key": key, "anthropic-version": "2023-06-01"}, timeout=timeout)
        r.raise_for_status()
        return sorted({str(x.get("id") or "").strip() for x in r.json().get("data", [])
                       if _compatible("anthropic", str(x.get("id") or ""))}, key=str.lower)

    key_name = f"{provider}_key"
    url_name = f"{provider}_url"
    base = (cfg.get(url_name) or _DEFAULT_URLS.get(provider) or "").strip().rstrip("/")
    key = (cfg.get(key_name) or "").strip()
    if provider == "custom":
        base = (cfg.get("custom_url") or "").strip().rstrip("/")
        key = (cfg.get("custom_key") or "").strip()
    if not base or (not key and not _local(base)):
        return []
    return _openai_compatible_models(provider, base, key, timeout)


def discover_all(cfg: dict, providers: tuple[str, ...] | None = None) -> tuple[dict, dict]:
    providers = providers or ("anthropic", "openai", "mistral", "kimi", "glm",
                              "ollama", "custom")
    models, errors = {}, {}
    for provider in providers:
        try:
            found = discover_provider(provider, cfg)
            if found:
                models[provider] = found
        except Exception as exc:
            errors[provider] = str(exc)
    return models, errors


class ModelDiscoveryWorker(QThread):
    done = pyqtSignal(dict, dict)  # modèles, erreurs par fournisseur

    def __init__(self, cfg: dict, providers: tuple[str, ...] | None = None, parent=None):
        super().__init__(parent)
        self._cfg = dict(cfg or {})
        self._providers = providers

    def run(self):
        self.done.emit(*discover_all(self._cfg, self._providers))
