import json
import os
import sys

# En mode gelé (PyInstaller installé dans Program Files), les données utilisateur
# vont dans %LOCALAPPDATA%\PANDORA\ (répertoire accessible en écriture sans UAC).
if getattr(sys, "frozen", False):
    _ROOT = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "PANDORA")
else:
    _ROOT = os.path.dirname(os.path.dirname(__file__))

_DATA_DIR = os.path.join(_ROOT, "data")
_CONFIG_FILE = os.path.join(_DATA_DIR, "config.json")

_DEFAULTS = {
    "api_key":               "",
    "anthropic_key":         "",
    "default_model":         "seedance-2.0",
    "default_duration":      "10",
    "default_resolution":    "720p",
    "output_dir":            "",   # vide = ~/Videos/PANDORA/
    "last_project_location": "",   # dernier dossier parent utilisé pour créer un projet
    # Modèle de génération d'images (castings, décors, accessoires, HMC, véhicules)
    "image_model":           "nb2",     # nb2 | nb_pro
    # Moteur vidéo alternatif (en plus de Seedance 2.0)
    "video_engine_alt":      "kling",   # kling | pixverse
    # Nano Banana Key (optionnel — même clé fal.ai si vide)
    "nano_banana_key":       "",
    # Charte d'utilisation — True = acceptée par l'utilisateur
    "eula_accepted":         False,
    # Guide de démarrage — True = afficher au premier lancement
    "show_api_guide":        True,
    # ── Assistant IA texte (voir core/ai_provider.py) ──────────────────────────
    "ai_provider":           "anthropic",          # compatibilité : fournisseur du choix simple
    "ai_profile":            "anthropic_optimized",# anthropic_optimized | openai_optimized | single | custom
    "ai_engine":             "",                   # clé du registre, ou provider:model-id découvert
    "ai_model_creative":     "claude-opus-4-8",    # défaut Opus 4.8 (Sonnet 5 / Fable 5 en option)
    "openai_key":            "",                   # clé OpenAI
    "openai_model":          "",                   # modèle OpenAI simple ; vide = registre/profil
    "mistral_key":           "",
    "ollama_url":            "",                   # vide = http://localhost:11434
    "ollama_model":          "",                   # vide = llama3.1
    "custom_key":            "",                   # fournisseur OpenAI-compatible personnalisé
    "custom_url":            "",
    "custom_model":          "",
    "ai_available_models":   {},                   # cache local {provider: [model-id]} découvert via API
    "ai_task_engines":       {},                   # {task_key: engine_key} — moteur par tâche
}

# ── Mapping modèle image → endpoint fal.ai ────────────────────────────────────
# Modèles à paramètre `image_size` (enum square_hd/portrait_4_3/…) plutôt que le
# couple `aspect_ratio`/`resolution` des Nano Banana → câblage dans nano_banana._build_image_args.
IMAGE_SIZE_MODELS = {"gpt2", "flux2", "seedream45", "recraft"}

IMAGE_MODEL_ENDPOINTS = {
    "nb2":        "fal-ai/nano-banana-2",
    "nb_pro":     "fal-ai/nano-banana-pro",
    "gpt2":       "openai/gpt-image-2",
    "flux2":      "fal-ai/flux-2-pro",
    "seedream45": "fal-ai/bytedance/seedream/v4.5/text-to-image",
    "recraft":    "fal-ai/recraft/v4.1/text-to-image",
}

IMAGE_MODEL_LABELS = {
    "nb2":        "Nano Banana 2  —  Gemini 3.1 Flash  ·  $0.08/img",
    "nb_pro":     "Nano Banana Pro  —  Gemini 3 Pro  ·  $0.15/img",
    "gpt2":       "GPT Image 2  —  OpenAI · suivi de prompt + texte  ·  ~$0.04/img",
    "flux2":      "FLUX.2 [pro]  —  photoréalisme  ·  ~$0.03/img",
    "seedream45": "Seedream 4.5  —  ByteDance · photoréalisme  ·  $0.04/img",
    "recraft":    "Recraft V4.1  —  texte / typo / logos  ·  $0.04/img",
}

IMAGE_MODEL_PRICES = {
    "nb2":        "$0.08",
    "nb_pro":     "$0.15",
    "gpt2":       "$0.04",
    "flux2":      "$0.03",
    "seedream45": "$0.04",
    "recraft":    "$0.04",
}


def get_image_endpoint(cfg: dict | None = None) -> str:
    """Retourne l'endpoint fal.ai du modèle image sélectionné dans la config.

    Les 6 modèles historiques sont mappés ici ; pour les moteurs élargis (catalogue
    complet PANDORA), on interroge core/image_engines (source unique)."""
    if cfg is None:
        cfg = load_config()
    model = cfg.get("image_model", "nb2")
    if model in IMAGE_MODEL_ENDPOINTS:
        return IMAGE_MODEL_ENDPOINTS[model]
    try:
        from core import image_engines as _ie
        if model in _ie.ENGINES:
            return _ie.ENGINES[model].get("endpoint", IMAGE_MODEL_ENDPOINTS["nb2"])
    except Exception:
        pass
    return IMAGE_MODEL_ENDPOINTS["nb2"]


def get_image_price(cfg: dict | None = None) -> str:
    """Retourne le prix formaté du modèle image sélectionné (catalogue complet)."""
    if cfg is None:
        cfg = load_config()
    model = cfg.get("image_model", "nb2")
    if model in IMAGE_MODEL_PRICES:
        return IMAGE_MODEL_PRICES[model]
    try:
        from core import image_engines as _ie
        return _ie.price_hint(model) or "$0.08"
    except Exception:
        return "$0.08"


def get_output_dir(cfg: dict | None = None) -> str:
    """Retourne le dossier de sortie des clips Seedance.

    Quand un projet est ouvert : <projet>/data/Seedance/
    Sinon : PANDORA/Seedance 2.0/ (dossier global)
    """
    from core.context import get_project_path
    project_path = get_project_path()
    if project_path:
        # Arborescence 2026-07-30 : cible 03_production/videos, replis legacy
        # « Studio IA » puis « Seedance » (core/project_layout — la table
        # généralise le mécanisme de repli né ici avec Seedance→Studio IA).
        from core import project_layout as _pl
        d = _pl.dir("videos", os.path.join(project_path, "data"))
        os.makedirs(d, exist_ok=True)
        return d
    from core.pandora_dirs import get_bin_dir
    return get_bin_dir("seedance", cfg)


def project_video_dir() -> str:
    """Dossier des vidéos générées du projet courant, pour la Vidéothèque :
    03_production/videos (replis legacy « Studio IA » puis « Seedance »)."""
    from core import project_layout as _pl
    return _pl.dir("videos")


def _migrate(cfg: dict) -> dict:
    """Migrations légères, idempotentes (drapeau one-shot)."""
    changed = False
    # Bascule UNIQUE de l'ancien défaut Sonnet 4.6 → Opus 4.8. Le choix de version
    # Claude est nouveau : personne n'avait choisi Sonnet délibérément avant.
    if not cfg.get("_opus_default_done"):
        if ((cfg.get("ai_model_creative") or "") in ("", "claude-sonnet-4-6")
                and (cfg.get("ai_provider") or "anthropic") == "anthropic"):
            cfg["ai_model_creative"] = "claude-opus-4-8"
        cfg["_opus_default_done"] = True
        changed = True
    if changed:
        try:
            save_config(cfg)
        except Exception:
            pass
    return cfg


def _atomic_write_json(path: str, data: dict) -> None:
    """Écriture ATOMIQUE (tmp + os.replace) : un crash pendant l'écriture ne
    laisse jamais un JSON tronqué. La config porte les clés API réelles, non
    restaurables — un fichier tronqué bloquait l'app au démarrage (audit
    2026-07-30). Pattern repris de ui/file_dialogs._save_prefs."""
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def load_config() -> dict:
    os.makedirs(_DATA_DIR, exist_ok=True)
    if os.path.exists(_CONFIG_FILE):
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                return _migrate(json.load(f))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            # Config corrompue (écriture interrompue d'avant l'atomicité) :
            # ne JAMAIS l'écraser — mise de côté horodatée pour récupérer les
            # clés API à la main, puis repli sur les défauts.
            try:
                import time as _t
                os.replace(_CONFIG_FILE,
                           f"{_CONFIG_FILE}.corrupt_{int(_t.time())}")
            except OSError:
                pass
            return dict(_DEFAULTS)
    return dict(_DEFAULTS)


def save_config(cfg: dict):
    os.makedirs(_DATA_DIR, exist_ok=True)
    _atomic_write_json(_CONFIG_FILE, cfg)
