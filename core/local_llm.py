"""core/local_llm.py — Les IA texte LOCALES au même niveau que Claude.

Ce que Claude fait sans qu'on le lui dise, un modèle local doit le faire
aussi. Quatre choses l'en empêchaient (audit du 24/09/2026 ; chantier demandé
par Matthieu : TOUS les moteurs, même les plus lourds, pour les essayer sur
d'autres machines) :

 1. Ollama coupait l'ENTRÉE en silence. Sans `num_ctx`, sa fenêtre vaut
    4 096 jetons (2 048 avant la 0.5) ; un scénario + les consignes + la
    sortie demandée en font 30 000. Le prompt système partait à la poubelle
    et le modèle répondait à la fin du texte, poliment, à côté.
    → `ollama_num_ctx()` dimensionne la fenêtre sur ce qui est ENVOYÉ
    (entrée estimée + sortie demandée), bornée par le contexte natif du
    modèle et par un plafond réglable (`ollama_num_ctx` dans la config).
 2. Les modèles « raisonnants » (Qwen3, DeepSeek-R1, GLM-4.x, gpt-oss…)
    pensent DANS la réponse — <think>…</think> — et la pensée mange le budget
    de sortie ; les analyseurs JSON de PANDORA s'y cassaient.
    → Ollama : `think: false` quand le modèle sait penser (l'équivalent du
    `thinking: disabled` envoyé à Anthropic) ; partout ailleurs :
    `strip_thinking()` sur les réponses et `ThinkFilter` sur les flux.
 3. Un modèle sans vision recevait les images et « décrivait » ce qu'il ne
    voyait pas. → `vision_error()` avant l'envoi, sur les capacités
    annoncées par Ollama.
 4. LM Studio, llama.cpp, vLLM et Jan n'existaient que derrière « fournisseur
    personnalisé » : ni préréglage, ni découverte des modèles, ni guide
    d'installation. → `LOCAL_PRESETS` + le fournisseur « local » de
    core/ai_provider, et quatre modules dans core/externals.

Module PUR : aucun réseau, tout se teste sans serveur.
"""

from __future__ import annotations

import math
import re

# ── Serveurs OpenAI-compatibles locaux : préréglages ─────────────────────────
# `think_kwargs` : le serveur accepte `chat_template_kwargs` (llama.cpp, vLLM,
# Jan = llama.cpp) → on y désactive la réflexion des modèles Qwen3-like ; les
# autres reçoivent une charge utile strictement OpenAI. `usage_stream` : le
# serveur renvoie la consommation en fin de flux si on la lui demande.

LOCAL_PRESETS: dict[str, dict] = {
    "lmstudio": {"name": "LM Studio", "url": "http://localhost:1234/v1",
                 "external": "lmstudio", "think_kwargs": False, "usage_stream": False},
    "llamacpp": {"name": "llama.cpp (llama-server)", "url": "http://localhost:8080/v1",
                 "external": "llamacpp", "think_kwargs": True, "usage_stream": True},
    "vllm":     {"name": "vLLM", "url": "http://localhost:8000/v1",
                 "external": "vllm", "think_kwargs": True, "usage_stream": True},
    "jan":      {"name": "Jan", "url": "http://localhost:1337/v1",
                 "external": "jan", "think_kwargs": True, "usage_stream": False},
    "other":    {"name": "Autre serveur OpenAI-compatible", "url": "http://localhost:8080/v1",
                 "external": "", "think_kwargs": False, "usage_stream": False},
}
DEFAULT_PRESET = "lmstudio"

#: Plafond par défaut de la fenêtre Ollama (jetons) — réglable dans la fenêtre
#: du module Ollama. 32 k couvre un scénario de ~60 000 caractères + 16 k de
#: sortie ; les grosses machines peuvent monter.
OLLAMA_CTX_DEFAULT = 32768
OLLAMA_CTX_FLOOR = 8192
OLLAMA_CTX_MAX = 262144


def preset(key: str) -> dict:
    return LOCAL_PRESETS.get((key or "").strip().lower()) or LOCAL_PRESETS[DEFAULT_PRESET]


def preset_key(cfg: dict | None) -> str:
    k = ((cfg or {}).get("local_preset") or "").strip().lower()
    return k if k in LOCAL_PRESETS else DEFAULT_PRESET


def preset_url(key: str) -> str:
    return preset(key)["url"]


def local_base_url(cfg: dict | None) -> str:
    """Adresse effective du serveur local : celle saisie, sinon celle du préréglage."""
    cfg = cfg or {}
    url = (cfg.get("local_url") or "").strip().rstrip("/")
    return url or preset_url(preset_key(cfg))


def external_for_preset(key: str) -> str:
    return preset(key)["external"]


# ── Modèles recommandés ──────────────────────────────────────────────────────
# Tailles VÉRIFIÉES chez registry.ollama.ai le 24/09/2026 (somme des couches).
# `vram` = mémoire vidéo pour tenir le modèle entièrement sur la carte ; en
# dessous, Ollama déborde sur la RAM et ralentit — ça marche, lentement.
# Décision Matthieu : la liste va jusqu'aux plus lourds (autres machines).

OLLAMA_MODELS: list[dict] = [
    {"name": "qwen3.5:latest",       "gb": 6.6,   "vram": 8,   "vision": False,
     "note": "Qwen 3.5 — le point de départ : français solide, JSON discipliné, 8 Go."},
    {"name": "qwen3:8b",             "gb": 5.2,   "vram": 8,   "vision": False,
     "note": "Qwen3 8B — classique éprouvé, réfléchit (PANDORA le désactive)."},
    {"name": "qwen3-vl:8b",          "gb": 6.1,   "vram": 8,   "vision": True,
     "note": "Qwen3-VL 8B — même famille AVEC la vision (analyse des références)."},
    {"name": "gemma3n:e4b",          "gb": 7.5,   "vram": 8,   "vision": True,
     "note": "Gemma 3n — conçu pour les petites machines, vision incluse."},
    {"name": "gemma3:12b",           "gb": 8.1,   "vram": 12,  "vision": True,
     "note": "Gemma 3 12B — très bon rédacteur, vision incluse."},
    {"name": "qwen3:14b",            "gb": 9.3,   "vram": 12,  "vision": False,
     "note": "Qwen3 14B — un cran au-dessus du 8B pour le découpage."},
    {"name": "gemma4:latest",        "gb": 9.6,   "vram": 12,  "vision": True,
     "note": "Gemma 4 — génération récente, vision incluse."},
    {"name": "gpt-oss:20b",          "gb": 13.8,  "vram": 16,  "vision": False,
     "note": "gpt-oss 20B (OpenAI, poids ouverts) — raisonnement fort, 16 Go."},
    {"name": "mistral-small3.2:24b", "gb": 15.2,  "vram": 16,  "vision": True,
     "note": "Mistral Small 3.2 — le meilleur français de la liste, vision incluse."},
    {"name": "qwen3.5:27b",          "gb": 17.4,  "vram": 24,  "vision": False,
     "note": "Qwen 3.5 27B — dense, pour une carte de 24 Go."},
    {"name": "gemma3:27b",           "gb": 17.4,  "vram": 24,  "vision": True,
     "note": "Gemma 3 27B — rédaction et vision, 24 Go."},
    {"name": "qwen3:30b-a3b",        "gb": 18.6,  "vram": 24,  "vision": False,
     "note": "Qwen3 30B-A3B — mélange d'experts : la qualité d'un 30B à la vitesse d'un 3B."},
    {"name": "qwen3:32b",            "gb": 20.2,  "vram": 24,  "vision": False,
     "note": "Qwen3 32B — dense, lent mais très sûr sur les longs documents."},
    {"name": "qwen3-vl:32b",         "gb": 20.9,  "vram": 24,  "vision": True,
     "note": "Qwen3-VL 32B — la vision au niveau du 32B."},
    {"name": "qwen3.6:latest",       "gb": 22.6,  "vram": 24,  "vision": True,
     "note": "Qwen 3.6 (36B, experts) — vision, réflexion, 262 k de contexte."},
    {"name": "llama3.3:70b",         "gb": 42.5,  "vram": 48,  "vision": False,
     "note": "Llama 3.3 70B — le grand classique, deux cartes ou une 48 Go."},
    {"name": "deepseek-r1:70b",      "gb": 42.5,  "vram": 48,  "vision": False,
     "note": "DeepSeek-R1 70B — raisonnement lourd (PANDORA masque la pensée)."},
    {"name": "gpt-oss:120b",         "gb": 65.4,  "vram": 80,  "vision": False,
     "note": "gpt-oss 120B — station de travail 80 Go."},
    {"name": "llama4:16x17b",        "gb": 67.4,  "vram": 80,  "vision": True,
     "note": "Llama 4 Scout — experts, vision, très long contexte."},
    {"name": "qwen3:235b-a22b",      "gb": 142.2, "vram": 160, "vision": False,
     "note": "Qwen3 235B-A22B — serveur multi-cartes : le plus fort de la liste."},
]

#: Dépôts GGUF (Hugging Face) pour `llama-server -hf` — existence vérifiée le
#: 24/09/2026. Le quantifieur Q4_K_M ≈ la taille des modèles Ollama ci-dessus.
GGUF_MODELS: list[dict] = [
    {"hf": "unsloth/Qwen3-8B-GGUF:Q4_K_M",                           "vram": 8,  "note": "Qwen3 8B"},
    {"hf": "unsloth/Qwen3-VL-8B-Instruct-GGUF:Q4_K_M",               "vram": 8,  "note": "Qwen3-VL 8B (vision)"},
    {"hf": "unsloth/gemma-3-12b-it-GGUF:Q4_K_M",                     "vram": 12, "note": "Gemma 3 12B"},
    {"hf": "unsloth/Qwen3-14B-GGUF:Q4_K_M",                          "vram": 12, "note": "Qwen3 14B"},
    {"hf": "ggml-org/gpt-oss-20b-GGUF",                              "vram": 16, "note": "gpt-oss 20B"},
    {"hf": "unsloth/Mistral-Small-3.2-24B-Instruct-2506-GGUF:Q4_K_M", "vram": 16, "note": "Mistral Small 3.2 24B"},
    {"hf": "unsloth/gemma-3-27b-it-GGUF:Q4_K_M",                     "vram": 24, "note": "Gemma 3 27B"},
    {"hf": "unsloth/Qwen3-30B-A3B-GGUF:Q4_K_M",                      "vram": 24, "note": "Qwen3 30B-A3B (experts)"},
    {"hf": "unsloth/Llama-3.3-70B-Instruct-GGUF:Q4_K_M",             "vram": 48, "note": "Llama 3.3 70B"},
    {"hf": "ggml-org/gpt-oss-120b-GGUF",                             "vram": 80, "note": "gpt-oss 120B"},
]


def model_label(m: dict) -> str:
    vis = "  ·  vision" if m.get("vision") else ""
    return f"{m['name']}  ·  {m['gb']:.0f} Go  ·  carte {m['vram']} Go{vis}"


# ── Ce qui n'est PAS un modèle de conversation ───────────────────────────────
# Les serveurs listent aussi les modèles d'embedding, de re-classement, de
# transcription… Les proposer comme assistant fait planter la première tâche.

_NOT_CHAT = ("embed", "rerank", "whisper", "tts", "speech", "moderation", "clip",
             "bge-", "e5-", "gte-", "nomic-", "transcribe", "vae", "ocr", "guard")


def is_chat_model(name: str) -> bool:
    low = (name or "").strip().lower()
    return bool(low) and not any(x in low for x in _NOT_CHAT)


# ── Fenêtre de contexte Ollama ───────────────────────────────────────────────

_CHARS_PER_TOKEN = 3.0        # français accentué : 3 à 3,5 caractères par jeton — on majore
_TOKENS_PER_IMAGE = 1500      # ordre de grandeur des jetons visuels d'une image


def estimate_tokens(messages: list, system: str = "") -> int:
    """Estimation HAUTE des jetons d'entrée (texte + images)."""
    chars = len(system or "")
    images = 0
    for m in messages or []:
        content = m.get("content", "") if isinstance(m, dict) else str(m)
        if isinstance(content, str):
            chars += len(content)
            continue
        for block in content or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                chars += len(block.get("text") or "")
            elif block.get("type") in ("image", "image_url"):
                images += 1
        images += len(m.get("images") or []) if isinstance(m, dict) else 0
    return int(math.ceil(chars / _CHARS_PER_TOKEN)) + images * _TOKENS_PER_IMAGE


def ollama_num_ctx(messages: list, max_tokens: int, system: str = "",
                   model_ctx: int = 0, ceiling: int = OLLAMA_CTX_DEFAULT) -> int:
    """La fenêtre qu'il FAUT pour cet appel : entrée estimée (+15 %) + sortie
    demandée + marge, arrondie au multiple de 2 048 supérieur, entre le plancher
    et le plafond réglé — jamais au-delà du contexte natif du modèle."""
    need = int(estimate_tokens(messages, system) * 1.15) + int(max_tokens or 0) + 512
    ctx = max(OLLAMA_CTX_FLOOR, int(math.ceil(need / 2048.0)) * 2048)
    ceiling = int(ceiling or OLLAMA_CTX_DEFAULT)
    ctx = min(ctx, max(OLLAMA_CTX_FLOOR, min(ceiling, OLLAMA_CTX_MAX)))
    if model_ctx and model_ctx > 0:
        ctx = min(ctx, int(model_ctx))
    return ctx


# ── Pensée des modèles raisonnants ───────────────────────────────────────────

_THINK_OPEN = re.compile(r"<(think|thinking|reasoning|thought)>", re.I)
_THINK_BLOCK = re.compile(r"<(think|thinking|reasoning|thought)>.*?</\1\s*>\s*", re.I | re.S)
_THINK_TAIL = re.compile(r"<(think|thinking|reasoning|thought)>.*\Z", re.I | re.S)


def strip_thinking(text: str) -> str:
    """Retire les blocs de pensée d'une réponse complète. Un bloc ouvert et
    jamais fermé (réponse coupée pendant la réflexion) est retiré jusqu'à la
    fin : ce n'était pas la réponse."""
    if not text or "<" not in text:
        return text or ""
    out = _THINK_BLOCK.sub("", text)
    out = _THINK_TAIL.sub("", out)
    return out.lstrip("\n") if out != text else out


class ThinkFilter:
    """Le même retrait, sur un FLUX : `feed(delta)` rend la part visible,
    `flush()` ce qui restait en attente. Les balises peuvent arriver coupées
    entre deux fragments (« <th » puis « ink> »)."""

    _TAGS = ("think", "thinking", "reasoning", "thought")
    _HOLD = 12                     # longueur max d'une balise ouvrante + marge

    def __init__(self):
        self._buf = ""
        self._hidden = False
        self._tag = ""

    def feed(self, delta: str) -> str:
        self._buf += delta or ""
        out = ""
        while True:
            if self._hidden:
                close = f"</{self._tag}>"
                i = self._buf.lower().find(close)
                if i < 0:
                    self._buf = self._buf[-len(close):]        # garde de quoi voir une fin coupée
                    return out
                self._buf = self._buf[i + len(close):].lstrip("\n")
                self._hidden = False
                continue
            m = _THINK_OPEN.search(self._buf)
            if m:
                out += self._buf[:m.start()]
                self._tag = m.group(1).lower()
                self._buf = self._buf[m.end():]
                self._hidden = True
                continue
            # Pas de balise : on rend tout, sauf un « < » récent qui pourrait en commencer une.
            lt = self._buf.rfind("<")
            if lt >= 0 and len(self._buf) - lt < self._HOLD and \
                    any(t.startswith(self._buf[lt + 1:].lower().rstrip(">")) for t in self._TAGS):
                out += self._buf[:lt]
                self._buf = self._buf[lt:]
            else:
                out += self._buf
                self._buf = ""
            return out

    def flush(self) -> str:
        rest = "" if self._hidden else self._buf
        self._buf, self._hidden = "", False
        return rest


# ── Vision ───────────────────────────────────────────────────────────────────

def has_images(messages: list) -> bool:
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        if m.get("images"):
            return True
        content = m.get("content")
        if isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") in ("image", "image_url") for b in content):
            return True
    return False


def vision_error(model: str, capabilities: list | None, messages: list) -> str:
    """Message d'erreur si l'appel porte des images et que le modèle ne les
    voit pas (capacités annoncées par Ollama) ; '' sinon. Capacités inconnues
    → on laisse passer (un vieux serveur ne les publie pas)."""
    if not has_images(messages) or capabilities is None:
        return ""
    if "vision" in [str(c).lower() for c in capabilities]:
        return ""
    return (f"Le modèle « {model} » ne voit pas les images. Pour l'analyse visuelle, "
            "choisissez un modèle avec la vision (qwen3-vl, gemma3, mistral-small3.2, "
            "llava…) — Paramètres → Assistant IA → moteur par tâche « Analyse visuelle ».")
