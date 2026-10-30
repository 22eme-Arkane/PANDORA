"""core/dictation.py — La dictée vocale d'ORAKLE dans PANDORA, côté moteur (sans Qt).

Demande Matthieu (27/10/2026) : « on intègre ORAKLE » — un micro dans tous les
champs de texte ; un clic = ORAKLE en mode mains-libres (on parle, on reclique, le
texte s'écrit), et les raccourcis d'ORAKLE (Ctrl+1 maintenu, ou deux fois) marchent
aussi. Choix : moteur EMBARQUÉ — PANDORA dicte même sans ORAKLE installé.

- Le micro et Whisper sont ceux d'ORAKLE, copiés tels quels dans orakle_engine/.
- Si ORAKLE est installé, ses réglages (raccourci, langues, modèle, micro) et son
  dictionnaire (termes favoris + corrections) sont repris en LECTURE SEULE : un mot
  ajouté dans ORAKLE profite aussi à PANDORA. Le modèle Whisper est partagé (même
  cache) : rien à retélécharger.
- Rien ne sort de la machine : la transcription est locale ; seul le modèle (≈ 480 Mo
  pour « small ») se télécharge une fois, après accord de l'utilisateur.
- Pas repris pour l'instant : la traduction parlée (« traduis en espagnol… ») et la
  sourdine des autres applications.

La partie Qt (micro dans les champs, raccourci, pastille) est ui/dictation.py.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
import threading
from importlib.util import find_spec
from typing import Optional

#: Clé de config PANDORA : micro affiché dans les champs (vrai par défaut).
CONFIG_KEY = "dictation_enabled"

#: Réglages d'ORAKLE utiles ici, avec ses valeurs par défaut (settings.default.json).
DEFAULTS = {
    "hotkey": "<ctrl>+1",
    "exclusive_hotkey": True,
    "hold_threshold_ms": 300,
    "double_tap_window_ms": 400,
    "languages": ["fr", "en", "es"],
    "force_language": None,
    "model": "small",
    "input_device": None,
    "device": "cpu",
    "compute_type": "int8",
    "append_trailing_space": True,
    "fast_transcription": False,
}

#: Taille approximative du téléchargement de chaque modèle (Mo), pour prévenir.
MODEL_SIZES_MB = {"tiny": 75, "base": 145, "small": 485, "medium": 1530,
                  "large-v2": 3090, "large-v3": 3090, "turbo": 1620,
                  "large-v3-turbo": 1620}
_MODEL_REPOS = {"turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
                "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo"}

#: En dessous, c'est un clic ou un tap involontaire : rien à transcrire.
MIN_AUDIO_SECONDS = 0.3
#: Comme ORAKLE : la langue est détectée PENDANT la dictée, dès ces secondes
#: captées — la transcription finale n'a plus à le faire (1,5 à 2,5 s gagnées).
EARLY_LANGUAGE_SECONDS = 3.0


# ── Réglages et dictionnaire d'ORAKLE (lecture seule) ─────────────────────────

def orakle_dir() -> str:
    """Le dossier utilisateur d'ORAKLE (même règle que son config.user_config_dir)."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"),
                                                         "AppData", "Roaming")
        return os.path.join(base, "orakle")
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support",
                            "orakle")
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"),
                                                             ".config")
    return os.path.join(base, "orakle")


def _read_json(name: str) -> dict:
    try:
        with open(os.path.join(orakle_dir(), name), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def orakle_installed() -> bool:
    """ORAKLE a déjà tourné sur ce compte (son dossier de réglages existe)."""
    return os.path.isfile(os.path.join(orakle_dir(), "settings.json"))


def settings() -> dict:
    """Les réglages d'ORAKLE s'il est installé, sinon ses valeurs par défaut.
    Chaque valeur lue garde le TYPE attendu, sinon le défaut s'applique."""
    out = dict(DEFAULTS)
    for key, value in _read_json("settings.json").items():
        if key not in DEFAULTS:
            continue
        default = DEFAULTS[key]
        if default is None:
            out[key] = value if (value is None or isinstance(value, (str, int))) else None
        elif isinstance(default, bool):
            if isinstance(value, bool):
                out[key] = value
        elif isinstance(default, int):
            if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                out[key] = value
        elif isinstance(default, list):
            if isinstance(value, list) and all(isinstance(v, str) for v in value):
                out[key] = [v.lower() for v in value]
        elif isinstance(value, str) and value.strip():
            out[key] = value.strip()
    return out


def dictionary() -> dict:
    """Le dictionnaire d'ORAKLE : {"bias_terms": [...], "corrections": {...}}."""
    data = _read_json("dictionary.json")
    bias = [str(t) for t in (data.get("bias_terms") or []) if str(t).strip()]
    corr = data.get("corrections") or {}
    corrections = ({str(k): str(v) for k, v in corr.items() if str(k).strip()}
                   if isinstance(corr, dict) else {})
    return {"bias_terms": bias, "corrections": corrections}


def initial_prompt(bias_terms: list) -> Optional[str]:
    """Biais de Whisper vers le vocabulaire perso (comme ORAKLE)."""
    return ", ".join(bias_terms) if bias_terms else None


def apply_corrections(text: str, corrections: dict) -> str:
    """Post-correction d'ORAKLE : mot entier, sans tenir compte de la casse."""
    out = text
    for wrong, right in (corrections or {}).items():
        if wrong:
            out = re.compile(r"\b" + re.escape(wrong) + r"\b", re.IGNORECASE).sub(right, out)
    return out


def hotkey_owned_by_orakle(cfg: Optional[dict] = None) -> bool:
    """ORAKLE tourne avec un raccourci NON exclusif : il écrit déjà lui-même au
    curseur, PANDORA doit s'effacer (sinon le texte arriverait deux fois). En mode
    exclusif (défaut d'ORAKLE), la touche ne parvient même pas à PANDORA."""
    cfg = cfg or settings()
    return (not cfg.get("exclusive_hotkey", True)
            and os.path.isfile(os.path.join(orakle_dir(), "orakle.lock")))


# ── Config PANDORA ────────────────────────────────────────────────────────────

def is_enabled(cfg: Optional[dict] = None) -> bool:
    if cfg is None:
        try:
            from core.config import load_config
            cfg = load_config()
        except Exception:
            cfg = {}
    return bool(cfg.get(CONFIG_KEY, True))


def set_enabled(enabled: bool) -> None:
    """save_config REMPLACE tout le fichier : on part toujours de la config entière."""
    from core.config import load_config, save_config
    cfg = load_config()
    cfg[CONFIG_KEY] = bool(enabled)
    save_config(cfg)


# ── Moteur ────────────────────────────────────────────────────────────────────

def engine_available() -> bool:
    """Micro (sounddevice) et Whisper (faster-whisper) présents dans l'installation."""
    try:
        return all(find_spec(m) is not None
                   for m in ("numpy", "sounddevice", "faster_whisper"))
    except (ImportError, ValueError):
        return False


def _hf_cache_dir() -> str:
    if os.environ.get("HF_HUB_CACHE"):
        return os.environ["HF_HUB_CACHE"]
    home = os.environ.get("HF_HOME") or os.path.join(os.path.expanduser("~"), ".cache",
                                                     "huggingface")
    return os.path.join(home, "hub")


def model_repo(name: str) -> str:
    if "/" in name:
        return name
    return _MODEL_REPOS.get(name, f"Systran/faster-whisper-{name}")


def model_cached(name: str) -> bool:
    """Le modèle est-il déjà téléchargé (cache Hugging Face, partagé avec ORAKLE) ?
    Lecture du disque seulement : importer faster-whisper coûte une seconde."""
    if os.path.isdir(name):
        return os.path.isfile(os.path.join(name, "model.bin"))
    folder = "models--" + model_repo(name).replace("/", "--")
    return bool(glob.glob(os.path.join(_hf_cache_dir(), folder, "snapshots", "*",
                                       "model.bin")))


def model_size_mb(name: str) -> int:
    return MODEL_SIZES_MB.get(name, 0)


class Engine:
    """Le micro et Whisper d'ORAKLE derrière quatre gestes : start, stop, cancel,
    transcribe. Thread-safe ; aucun appel réseau sauf le premier téléchargement du
    modèle (fait par faster-whisper, au premier warm/transcribe)."""

    def __init__(self, cfg: Optional[dict] = None):
        self.cfg = dict(cfg or settings())
        self._recorder = None
        self._transcriber = None
        self._lock = threading.Lock()
        self._warm_thread: Optional[threading.Thread] = None
        self._lang: Optional[str] = None
        self._lang_thread: Optional[threading.Thread] = None

    # micro
    def _rec(self):
        if self._recorder is None:
            from orakle_engine.recorder import Recorder
            self._recorder = Recorder(device=self.cfg.get("input_device"))
        return self._recorder

    @property
    def is_recording(self) -> bool:
        return bool(self._recorder is not None and self._recorder.is_recording)

    @property
    def level(self) -> float:
        return self._recorder.level if self._recorder is not None else 0.0

    def start(self) -> None:
        """Ouvre le micro au besoin (quelques centaines de ms la 1re fois) et arme
        la capture. Lève si aucun micro n'est utilisable."""
        self._rec().start()
        self._lang = None
        self._lang_thread = None

    def prefetch_language(self) -> None:
        """Pendant l'écoute (appelé régulièrement) : dès ~3 s captées, la langue
        parlée est détectée en tâche de fond sur ce qui a été dit jusque-là."""
        rec = self._recorder
        if (self.cfg.get("force_language") or self._lang_thread is not None
                or rec is None or not rec.is_recording
                or rec.captured_seconds < EARLY_LANGUAGE_SECONDS):
            return
        snapshot = rec.snapshot()
        tr = self._tr()

        def job():
            try:
                self._lang = tr.detect(snapshot)[0]
            except Exception:
                self._lang = None

        self._lang_thread = threading.Thread(target=job, name="pandora-dictation-lang",
                                             daemon=True)
        self._lang_thread.start()

    def stop(self):
        """Fin de la capture : l'audio (numpy float32 mono 16 kHz) ou None."""
        return self._recorder.stop() if self._recorder is not None else None

    def cancel(self) -> None:
        if self._recorder is not None:
            self._recorder.stop()

    def release_mic(self) -> None:
        """Ferme le micro (Windows cesse d'afficher « micro utilisé »)."""
        if self._recorder is not None and not self._recorder.is_recording:
            self._recorder.close()

    # Whisper
    def _tr(self):
        with self._lock:
            if self._transcriber is None:
                from orakle_engine.transcriber import Transcriber
                self._transcriber = Transcriber(
                    model=self.cfg.get("model", "small"),
                    device=self.cfg.get("device", "cpu"),
                    compute_type=self.cfg.get("compute_type", "int8"),
                    languages=self.cfg.get("languages"),
                    fast=bool(self.cfg.get("fast_transcription", False)),
                )
            return self._transcriber

    def warm_async(self) -> None:
        """Charge (et télécharge au besoin) Whisper en tâche de fond, pendant que
        l'utilisateur parle : la transcription attendra la fin de ce chargement."""
        if self._warm_thread is not None and self._warm_thread.is_alive():
            return
        tr = self._tr()
        if getattr(tr, "_model", None) is not None:
            return
        self._warm_thread = threading.Thread(target=tr.warm, name="pandora-dictation-warm",
                                             daemon=True)
        self._warm_thread.start()

    def transcribe(self, audio) -> str:
        """Texte dicté, corrigé par le dictionnaire d'ORAKLE ("" si rien d'audible)."""
        if audio is None or len(audio) < MIN_AUDIO_SECONDS * 16_000:
            return ""
        words = dictionary()
        language = self.cfg.get("force_language") or None
        if not language and self._lang_thread is not None:
            self._lang_thread.join(timeout=15)
            language = self._lang
        text = self._tr().transcribe(
            audio,
            language=language,
            initial_prompt=initial_prompt(words["bias_terms"]),
        )
        return apply_corrections(text or "", words["corrections"]).strip()

    @property
    def model_loaded(self) -> bool:
        return getattr(self._transcriber, "_model", None) is not None

    def release_model(self) -> None:
        """Libère la mémoire de Whisper après une longue inactivité (rechargé à la
        dictée suivante)."""
        with self._lock:
            tr = self._transcriber
            if tr is None or (self._warm_thread is not None and self._warm_thread.is_alive()):
                return
            self._transcriber = None


_ENGINE: Optional[Engine] = None


def engine() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = Engine()
    return _ENGINE


# ── Raccourci : la machine à états d'ORAKLE (orakle/hotkey.py), sans pynput ───

def hotkey_parts(hotkey: str) -> tuple[frozenset, str]:
    """'<ctrl>+1' -> ({'ctrl'}, '1') ; '<ctrl>+<shift>+<f9>' -> ({'ctrl','shift'}, 'f9')."""
    mods, main = set(), ""
    for part in str(hotkey or "").split("+"):
        token = part.strip().strip("<>").lower()
        if token in ("ctrl", "control", "ctrl_l", "ctrl_r"):
            mods.add("ctrl")
        elif token in ("shift", "shift_l", "shift_r"):
            mods.add("shift")
        elif token in ("alt", "alt_l", "alt_r", "alt_gr"):
            mods.add("alt")
        elif token in ("cmd", "win", "super", "meta"):
            mods.add("cmd")
        elif token:
            main = token
    if not main:
        return hotkey_parts(DEFAULTS["hotkey"])
    return frozenset(mods), main


def hotkey_label(hotkey: str) -> str:
    """'<ctrl>+1' -> 'Ctrl+1' (texte des infobulles)."""
    mods, main = hotkey_parts(hotkey)
    names = {"ctrl": "Ctrl", "shift": "Maj", "alt": "Alt", "cmd": "Cmd"}
    order = [names[m] for m in ("ctrl", "alt", "shift", "cmd") if m in mods]
    return "+".join(order + [main.upper() if len(main) <= 3 else main.capitalize()])


class HotkeyMachine:
    """Un seul raccourci, deux modes, comme ORAKLE :

    - maintien (≥ hold) : on parle tant que la touche est enfoncée, on relâche → écrit ;
    - deux appuis brefs rapprochés (≤ double_tap) : mains-libres ; un appui bref
      suivant ferme et écrit ;
    - un appui bref isolé : rien.

    Pur et piloté par l'horloge qu'on lui passe (testable). Chaque geste renvoie la
    liste des actions à faire : "start" (capture tentative), "confirm" (capture
    confirmée → montrer la pastille), "commit" (arrêter et écrire), "cancel" (jeter).
    """

    def __init__(self, hold_ms: int = 300, double_tap_ms: int = 400):
        self.hold = max(0, hold_ms) / 1000.0
        self.double_tap = max(0, double_tap_ms) / 1000.0
        self.reset()

    def reset(self) -> None:
        self.engaged = False      # touche principale enfoncée (anti-répétition)
        self.recording = False
        self.mode: Optional[str] = None   # None | "hold" | "toggle"
        self.confirmed = False
        self.closing = False      # le relâchement en cours ferme le mains-libres
        self.t_down = 0.0
        self.last_tap: Optional[float] = None

    def enter_toggle(self) -> None:
        """Le mains-libres a été ouvert autrement (clic sur le micro) : le prochain
        appui bref du raccourci le fermera."""
        self.reset()
        self.recording = True
        self.mode = "toggle"
        self.confirmed = True

    def press(self, now: float) -> list:
        if self.engaged:
            return []
        self.engaged = True
        if self.mode == "toggle":
            self.closing = True
            return []
        self.t_down = now
        self.recording = True
        self.confirmed = False
        return ["start"]

    def tick(self, now: float) -> list:
        """Appelé pendant l'appui : la capture devient un vrai maintien."""
        if (self.engaged and self.recording and self.mode is None and not self.confirmed
                and now - self.t_down >= self.hold):
            self.confirmed = True
            self.mode = "hold"
            return ["confirm"]
        return []

    def release(self, now: float) -> list:
        if not self.engaged:
            return []
        self.engaged = False
        if self.closing:
            self.reset()
            return ["commit"]
        if not self.recording:
            return []
        if now - self.t_down >= self.hold:
            acts = [] if self.confirmed else ["confirm"]
            self.reset()
            return acts + ["commit"]
        # Appui bref : peut-être le 1er d'un double appui.
        self.recording = False
        self.mode = None
        acts = ["cancel"]
        if self.last_tap is not None and now - self.last_tap <= self.double_tap:
            self.last_tap = None
            self.mode = "toggle"
            self.recording = True
            self.confirmed = True
            acts += ["start", "confirm"]
        else:
            self.last_tap = now
        return acts


# ── Insertion dans le texte ───────────────────────────────────────────────────

_NO_SPACE_AFTER = "([{«“‘'’\"/-\n\t "
_NO_SPACE_BEFORE = ".,;:!?)]}»”’…\n\t "


def spaced(before: str, text: str, after: str, trailing_space: bool = True) -> str:
    """Le texte dicté prêt à insérer entre `before` et `after` : un espace devant
    s'il colle au mot précédent, un espace derrière (réglage d'ORAKLE) sauf devant
    un espace ou une ponctuation."""
    text = (text or "").strip()
    if not text:
        return ""
    if before and before[-1] not in _NO_SPACE_AFTER and text[0] not in _NO_SPACE_BEFORE:
        text = " " + text
    if trailing_space and (not after or after[0] not in _NO_SPACE_BEFORE):
        text += " "
    return text
