"""core/externals.py — Registre des modules EXTERNES à PANDORA.

Certaines fonctions s'appuient sur un logiciel qui n'est PAS livré avec PANDORA
(taille, licences) : ComfyUI Desktop et ses modèles MiniMax H3, le serveur
sd.cpp du projet communautaire minimax-h3-local, Ollama pour une IA texte
locale. Jusqu'au 24/09/2026 chacun avait son sort : ComfyUI une fenêtre avec
des liens, H3 local une phrase dans les Paramètres, Ollama rien du tout
(constat Matthieu). Ici, UNE source : pour chaque module, ce qu'il apporte,
comment le détecter, où le télécharger, la marche à suivre, la licence, et ce
que PANDORA sait installer lui-même (voir api/external_install).

Trois moments l'utilisent : le bandeau sous le choix du moteur
(ui/external_banner), la fenêtre proposée au clic « Générer »
(ui/dialog_external) et la section « Modules externes » des Paramètres
(ui/externals_section).

Décision Matthieu : PANDORA n'embarque rien ; il détecte, guide, télécharge
et lance — sous les yeux de l'utilisateur, jamais sans un clic.

Module PUR sauf `detect()`, qui sonde des serveurs locaux (2 s max) : à
appeler depuis un worker, jamais depuis le thread de l'interface.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field

# Taille annoncée des cinq fichiers H3 des gabarits officiels (relevé 23/09/2026 :
# 21 + 15,7 + 5,2 + 0,6 + 2 Go). Sert au message avant téléchargement.
H3_MODELS_TOTAL_GB = 45

#: Archive du projet communautaire (aucune release publiée — relevé 24/09/2026).
H3_LOCAL_REPO = "ksl16012001/minimax-h3-local"
H3_LOCAL_ARCHIVE_URL = f"https://github.com/{H3_LOCAL_REPO}/archive/refs/heads/main.zip"
#: Palier de setup.bat installé par PANDORA : Q3 + LoRA turbo 8 pas, ~28 Go —
#: celui qui correspond au préréglage « rapide » de core/h3_local.
H3_LOCAL_TIER = "recommended"
H3_LOCAL_TIER_GB = 28

OLLAMA_DEFAULT_MODEL = "llama3.1"


@dataclass(frozen=True)
class External:
    key: str
    name: str
    purpose: str                   # à quoi ça sert, en une phrase (FR)
    download_url: str              # page ou fichier officiel
    docs_url: str                  # guide
    steps: tuple                   # marche à suivre (FR)
    license_note: str = ""         # avis affiché en ambre, "" si aucun
    engine_keys: tuple = ()        # clés de moteur / fournisseur qui en dépendent
    url_config_key: str = ""       # réglage d'adresse du serveur, "" si aucun
    auto_install: bool = False     # PANDORA sait télécharger et lancer l'installation


@dataclass
class Status:
    installed: bool = False
    running: bool = False
    version: str = ""
    detail: str = ""               # phrase lisible (FR)
    missing: list = field(default_factory=list)      # fichiers de modèles absents
    checked: bool = True           # False = pas encore sondé

    @property
    def ready(self) -> bool:
        return self.running and not self.missing


def _h3_license() -> str:
    try:
        from core.h3_local import LICENSE_NOTICE
        return LICENSE_NOTICE
    except Exception:
        return ""


EXTERNALS: dict[str, External] = {
    "comfyui": External(
        key="comfyui",
        name="ComfyUI Desktop",
        purpose="Le rendu vidéo LOCAL par défaut de PANDORA : MiniMax H3 sur votre "
                "carte graphique, et tout workflow ComfyUI personnalisé. 0 $ par clip.",
        download_url="https://download.comfy.org/windows/nsis/x64",
        docs_url="https://docs.comfy.org/tutorials/video/minimax/minimax-h3",
        steps=(
            "Installer ComfyUI Desktop (installeur officiel, ~180 Mo) et le lancer une "
            "première fois jusqu'à ce que son interface s'affiche.",
            f"Télécharger les modèles MiniMax H3 (5 fichiers, ~{H3_MODELS_TOTAL_GB} Go) : "
            "PANDORA peut le faire pour vous, dans le dossier de modèles de ComfyUI.",
            "Laisser ComfyUI Desktop ouvert pendant les rendus, puis « Tester » ici.",
        ),
        license_note=_h3_license(),
        engine_keys=("comfy", "comfy_h3_t2v", "comfy_h3_i2v", "comfy_custom"),
        url_config_key="comfy_url",
        auto_install=True,
    ),
    "h3_local": External(
        key="h3_local",
        name="MiniMax H3 local (serveur sd.cpp)",
        purpose="MiniMax H3 sans ComfyUI, sur une carte de 8 Go : un binaire CUDA et "
                "des poids GGUF, servis sur le port 1234 (projet communautaire "
                "minimax-h3-local). 0 $ par clip.",
        download_url=f"https://github.com/{H3_LOCAL_REPO}",
        docs_url=f"https://github.com/{H3_LOCAL_REPO}#readme",
        steps=(
            "PANDORA télécharge les scripts du projet dans son dossier de modules.",
            f"Une console s'ouvre et exécute « setup.bat {H3_LOCAL_TIER} » "
            f"(binaires + modèles, ~{H3_LOCAL_TIER_GB} Go) — gardez-la ouverte jusqu'à la fin.",
            "« Lancer le serveur » démarre start_server.ps1 (port 1234) ; puis « Tester ».",
        ),
        license_note=_h3_license(),
        engine_keys=("minimax-h3-local", "h3local_t2v", "h3local_i2v"),
        url_config_key="h3_local_url",
        auto_install=True,
    ),
    "ollama": External(
        key="ollama",
        name="Ollama",
        purpose="Une IA texte qui tourne sur votre machine (assistant, analyses) : "
                "aucune clé, aucun crédit, vos textes ne quittent pas l'ordinateur.",
        download_url="https://ollama.com/download/OllamaSetup.exe",
        docs_url="https://ollama.com/library",
        steps=(
            "Installer Ollama (installeur officiel) — il démarre ensuite tout seul.",
            "Télécharger un modèle : PANDORA en propose une liste (Qwen, Gemma, Mistral, "
            "gpt-oss, Llama… de 5 Go aux plus lourds) et le télécharge pour vous.",
            "Choisir « Ollama local » dans l'Assistant IA des Paramètres.",
        ),
        engine_keys=("ollama",),
        url_config_key="ollama_url",
        auto_install=True,
    ),
    # ── Serveurs OpenAI-compatibles locaux (fournisseur « local », préréglages
    # dans core/local_llm) — chantier IA locales du 24/09/2026 ─────────────
    "lmstudio": External(
        key="lmstudio",
        name="LM Studio",
        purpose="IA texte locale avec une interface : catalogue de modèles GGUF, "
                "chargement en un clic, serveur OpenAI-compatible (port 1234). PANDORA "
                "s'y connecte comme à Claude. Aucune clé, aucun crédit.",
        download_url="https://lmstudio.ai/download/latest/win32/x64",
        docs_url="https://lmstudio.ai/docs/app/api",
        steps=(
            "Installer LM Studio (installeur officiel) et télécharger un modèle dans son "
            "onglet Découvrir (Qwen3, Gemma 3, Mistral Small… selon votre carte).",
            "Charger le modèle avec une fenêtre de contexte d'au moins 32 000 jetons "
            "(réglage du chargement), puis démarrer le serveur local (onglet Développeur).",
            "Dans PANDORA : Assistant IA → « Serveur IA local », préréglage LM Studio, "
            "« Tester » liste les modèles chargés.",
        ),
        engine_keys=("local:lmstudio",),
        url_config_key="local_url",
        auto_install=True,
    ),
    "llamacpp": External(
        key="llamacpp",
        name="llama.cpp (llama-server)",
        purpose="Le moteur de référence des modèles GGUF, sans interface : un exécutable, "
                "un modèle pris sur Hugging Face, un port (8080). Le plus léger et le "
                "plus rapide sur une carte NVIDIA.",
        download_url="https://github.com/ggml-org/llama.cpp/releases",
        docs_url="https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md",
        steps=(
            "PANDORA télécharge la dernière version Windows (CUDA si une carte NVIDIA est "
            "détectée, sinon CPU) dans son dossier de modules.",
            "« Lancer » ouvre une console : llama-server télécharge le modèle GGUF choisi "
            "(Hugging Face) au premier démarrage, puis sert le port 8080.",
            "Dans PANDORA : Assistant IA → « Serveur IA local », préréglage llama.cpp.",
        ),
        engine_keys=("local:llamacpp",),
        url_config_key="local_url",
        auto_install=True,
    ),
    "vllm": External(
        key="vllm",
        name="vLLM",
        purpose="Serveur haute performance pour les GROS modèles, sur une ou plusieurs "
                "cartes (Linux ou WSL sous Windows). Port 8000, API OpenAI-compatible.",
        download_url="https://docs.vllm.ai/en/latest/getting_started/installation/",
        docs_url="https://docs.vllm.ai/",
        steps=(
            "Installer vLLM sur une machine Linux (ou WSL) : « pip install vllm » dans un "
            "environnement Python avec CUDA — voir le guide.",
            "Démarrer « vllm serve <modèle> --port 8000 » ; le serveur télécharge le modèle "
            "depuis Hugging Face.",
            "Dans PANDORA : Assistant IA → « Serveur IA local », préréglage vLLM, adresse "
            "de la machine si elle n'est pas celle-ci.",
        ),
        engine_keys=("local:vllm",),
        url_config_key="local_url",
        auto_install=False,
    ),
    "jan": External(
        key="jan",
        name="Jan",
        purpose="Application open source : catalogue de modèles, interface de chat et "
                "serveur OpenAI-compatible local (port 1337).",
        download_url="https://github.com/janhq/jan/releases/latest",
        docs_url="https://jan.ai/docs",
        steps=(
            "Installer Jan (installeur officiel) et télécharger un modèle dans son Hub.",
            "Activer le serveur local dans Jan (Paramètres → Serveur local, port 1337).",
            "Dans PANDORA : Assistant IA → « Serveur IA local », préréglage Jan.",
        ),
        engine_keys=("local:jan",),
        url_config_key="local_url",
        auto_install=True,
    ),
}

#: Les modules qui servent le fournisseur « local » (clé du préréglage = clé du module).
LOCAL_SERVER_KEYS = ("lmstudio", "llamacpp", "vllm", "jan")


def for_engine(engine_key: str) -> External | None:
    """Le module externe dont dépend un moteur (clé d'onglet ou de Studio)."""
    for ext in EXTERNALS.values():
        if engine_key in ext.engine_keys:
            return ext
    return None


# ── Dossiers et exécutables ──────────────────────────────────────────────────

def externals_dir() -> str:
    """Là où PANDORA range ce qu'il télécharge (%LOCALAPPDATA%\\PANDORA\\externals)."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "PANDORA", "externals")
    os.makedirs(d, exist_ok=True)
    return d


def comfy_desktop_exe() -> str:
    la = os.environ.get("LOCALAPPDATA", "")
    for p in (os.path.join(la, "Programs", "Comfy Desktop", "Comfy Desktop.exe"),
              os.path.join(os.environ.get("PROGRAMFILES", ""), "Comfy Desktop", "Comfy Desktop.exe")):
        if p and os.path.isfile(p):
            return p
    return ""


def comfy_models_dir() -> str:
    """Dossier de modèles de ComfyUI Desktop (settings.json → modelsDirs), sinon
    l'emplacement partagé par défaut s'il existe, sinon ''."""
    appdata = os.environ.get("APPDATA", "")
    settings = os.path.join(appdata, "Comfy Desktop", "settings.json")
    try:
        with open(settings, encoding="utf-8") as f:
            dirs = json.load(f).get("modelsDirs") or []
        for d in dirs:
            if d and os.path.isdir(d):
                return d
    except Exception:
        pass
    default = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Comfy-Desktop", "ComfyUI-Shared", "models")
    return default if os.path.isdir(default) else ""


def ollama_exe() -> str:
    la = os.environ.get("LOCALAPPDATA", "")
    for p in (os.path.join(la, "Programs", "Ollama", "ollama app.exe"),
              os.path.join(la, "Programs", "Ollama", "ollama.exe")):
        if os.path.isfile(p):
            return p
    return shutil.which("ollama") or ""


def _first_file(*paths: str) -> str:
    for p in paths:
        if p and os.path.isfile(p):
            return p
    return ""


def lmstudio_exe() -> str:
    la, pf = os.environ.get("LOCALAPPDATA", ""), os.environ.get("PROGRAMFILES", "")
    return _first_file(os.path.join(la, "Programs", "LM Studio", "LM Studio.exe"),
                       os.path.join(la, "LM-Studio", "LM Studio.exe"),
                       os.path.join(pf, "LM Studio", "LM Studio.exe"))


def lms_cli() -> str:
    """L'outil en ligne de commande de LM Studio (« lms server start ») — il
    permet de démarrer le serveur sans passer par l'interface."""
    home = os.path.expanduser("~")
    return _first_file(os.path.join(home, ".lmstudio", "bin", "lms.exe"),
                       os.path.join(home, ".cache", "lm-studio", "bin", "lms.exe")) \
        or (shutil.which("lms") or "")


def jan_exe() -> str:
    la, pf = os.environ.get("LOCALAPPDATA", ""), os.environ.get("PROGRAMFILES", "")
    return _first_file(os.path.join(la, "Programs", "jan", "Jan.exe"),
                       os.path.join(la, "Programs", "Jan", "Jan.exe"),
                       os.path.join(pf, "Jan", "Jan.exe"))


def llamacpp_dir() -> str:
    return os.path.join(externals_dir(), "llama.cpp")


def llama_server_exe() -> str:
    return _first_file(os.path.join(llamacpp_dir(), "llama-server.exe")) \
        or (shutil.which("llama-server") or "")


def nvidia_gpu_present() -> bool:
    return bool(shutil.which("nvidia-smi")
                or os.path.isfile(os.path.join(os.environ.get("SYSTEMROOT", r"C:\Windows"),
                                               "System32", "nvidia-smi.exe")))


def h3_local_dir() -> str:
    return os.path.join(externals_dir(), "minimax-h3-local")


def h3_local_installed() -> bool:
    return os.path.isfile(os.path.join(h3_local_dir(), "start_server.ps1"))


# ── Modèles H3 des gabarits officiels ────────────────────────────────────────

def h3_models_required() -> list[dict]:
    """Les fichiers de modèles que les gabarits H3 embarqués déclarent
    (`properties.models` : name, directory, url) — SANS liste écrite à la
    main : c'est ce que ComfyUI télécharge lui-même en ouvrant le gabarit."""
    from core import comfy_h3 as _h3c
    from core import comfy_workflow as _wf
    seen: dict[str, dict] = {}
    for key in _h3c.TEMPLATES:
        path = _h3c.template_path(key)
        try:
            wf = _wf.load(path)
        except Exception:
            continue
        nodes = list(wf.get("nodes") or [])
        for sg in (wf.get("definitions") or {}).get("subgraphs") or []:
            nodes.extend(sg.get("nodes") or [])
        for n in nodes:
            for m in (n.get("properties") or {}).get("models") or []:
                name, url, d = m.get("name"), m.get("url"), m.get("directory")
                if name and url and d and name not in seen:
                    seen[name] = {"name": name, "url": url, "directory": d}
    return list(seen.values())


def h3_models_missing(models_dir: str) -> list[dict]:
    """Ceux qui ne sont pas (complètement) dans le dossier de modèles : un
    `.part` en cours de téléchargement compte comme absent."""
    return models_missing(h3_models_required(), models_dir)


def models_missing(required: list[dict], models_dir: str) -> list[dict]:
    if not models_dir:
        return list(required)
    return [m for m in required
            if not os.path.isfile(os.path.join(models_dir, m["directory"], m["name"]))]


def _models_of_workflow(wf: dict) -> list[dict]:
    seen: dict[str, dict] = {}
    nodes = list(wf.get("nodes") or [])
    for sg in (wf.get("definitions") or {}).get("subgraphs") or []:
        nodes.extend(sg.get("nodes") or [])
    for n in nodes:
        for m in (n.get("properties") or {}).get("models") or []:
            name, url, d = m.get("name"), m.get("url"), m.get("directory")
            if name and url and d and name not in seen:
                seen[name] = {"name": name, "url": url, "directory": d}
    return list(seen.values())


def template_models(name: str) -> list[dict]:
    """Les fichiers de modèles qu'un gabarit officiel d'IMAGE déclare — lus
    dans sa copie locale (core/comfy_image.load_template la range dans le
    dossier des modules quand ComfyUI répond). Vide si le gabarit n'a jamais
    été chargé."""
    from core import comfy_workflow as _wf
    path = os.path.join(externals_dir(), "comfy_templates", f"{name}.json")
    if not os.path.isfile(path):
        return []
    try:
        return _models_of_workflow(_wf.load(path))
    except Exception:
        return []


# ── Détection ────────────────────────────────────────────────────────────────

def _ollama_url() -> str:
    try:
        from core.config import load_config
        u = (load_config().get("ollama_url") or "").strip().rstrip("/")
    except Exception:
        u = ""
    return u or "http://localhost:11434"


def _get_json(url: str, timeout: float = 2.0):
    import urllib.request
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def detect(key: str) -> Status:
    """État d'un module : installé ? en marche ? modèles présents ? Sonde les
    serveurs locaux (2 s max chacun) — depuis un worker."""
    if key == "comfyui":
        from core import comfy as _cf
        st = Status(installed=bool(comfy_desktop_exe()) or _cf.desktop_installed())
        base = _cf.discover()
        if base:
            ok, _msg, info = _cf.ping(base)
            st.running, st.version, st.installed = ok, str(info.get("version") or ""), True
        md = comfy_models_dir()
        st.missing = [m["name"] for m in h3_models_missing(md)] if md else []
        if not st.installed:
            st.detail = "ComfyUI Desktop n'est pas installé sur cet ordinateur."
        elif not st.running:
            st.detail = "ComfyUI Desktop est installé mais ne tourne pas."
        elif st.missing:
            st.detail = (f"ComfyUI {st.version} en marche — {len(st.missing)} fichier(s) "
                         f"de modèle MiniMax H3 manquant(s).")
        else:
            st.detail = f"ComfyUI {st.version} en marche, modèles MiniMax H3 présents."
        return st
    if key == "h3_local":
        from core import h3_local as _h3l
        ok, msg = _h3l.ping(_h3l.get_url())
        st = Status(installed=h3_local_installed() or ok, running=ok)
        if ok:
            st.detail = "Serveur MiniMax H3 local en marche."
        elif st.installed:
            st.detail = "Projet installé, serveur arrêté — « Lancer le serveur »."
        else:
            st.detail = "Le serveur MiniMax H3 local n'est pas installé (ou pas lancé) : " + str(msg)
        return st
    if key == "ollama":
        st = Status(installed=bool(ollama_exe()))
        try:
            v = _get_json(_ollama_url() + "/api/version")
            st.running, st.installed = True, True
            st.version = str(v.get("version") or "")
        except Exception:
            st.running = False
        if st.running:
            try:
                from core.config import load_config
                want = (load_config().get("ollama_model") or OLLAMA_DEFAULT_MODEL).strip()
            except Exception:
                want = OLLAMA_DEFAULT_MODEL
            try:
                names = [m.get("name", "") for m in _get_json(_ollama_url() + "/api/tags").get("models") or []]
                if not any(n == want or n.split(":")[0] == want.split(":")[0] for n in names):
                    st.missing = [want]
            except Exception:
                pass
        if not st.installed:
            st.detail = "Ollama n'est pas installé sur cet ordinateur."
        elif not st.running:
            st.detail = "Ollama est installé mais ne tourne pas."
        elif st.missing:
            st.detail = f"Ollama {st.version} en marche — modèle « {st.missing[0]} » à télécharger."
        else:
            st.detail = f"Ollama {st.version} en marche, modèle prêt."
        return st
    if key in LOCAL_SERVER_KEYS:
        return _detect_openai_server(key)
    return Status(detail=f"Module inconnu : {key}", checked=False)


def local_server_url(key: str) -> str:
    """Adresse d'un serveur local : celle saisie dans les Paramètres si le
    préréglage courant est ce module, sinon celle du préréglage."""
    from core.local_llm import preset_url
    try:
        from core.config import load_config
        cfg = load_config()
        if (cfg.get("local_preset") or "").strip().lower() == key and (cfg.get("local_url") or "").strip():
            return cfg["local_url"].strip().rstrip("/")
    except Exception:
        pass
    return preset_url(key)


def _detect_openai_server(key: str) -> Status:
    exe = {"lmstudio": lmstudio_exe, "jan": jan_exe, "llamacpp": llama_server_exe}.get(key, lambda: "")()
    st = Status(installed=bool(exe))
    base = local_server_url(key)
    name = EXTERNALS[key].name
    try:
        j = _get_json(base + "/models")
        st.running = st.installed = True
        names = [str(m.get("id") if isinstance(m, dict) else m) for m in (j.get("data") or [])]
        st.version = f"{len(names)} modèle(s)"
        if not names:
            st.missing = ["(aucun modèle chargé)"]
    except Exception:
        st.running = False
    if not st.installed:
        st.detail = f"{name} n'est pas installé sur cet ordinateur (ou son serveur ne répond pas sur {base})."
    elif not st.running:
        st.detail = f"{name} est installé mais son serveur ne répond pas sur {base}."
    elif st.missing:
        st.detail = f"{name} répond sur {base} — aucun modèle chargé : chargez-en un dans l'application."
    else:
        st.detail = f"{name} en marche sur {base} — {st.version}."
    return st
