"""
api/music.py — Workers de GÉNÉRATION MUSICALE pour le Studio IA (onglet « Musique IA »).

Catalogue multi-moteurs fal.ai (vérifié 2026-06-15) + worker unique `MusicWorker`
qui bascule mock ↔ réel selon la présence de la clé fal.ai (`api_key` de config.json),
sur le même pattern que api/tts.py (SFX 1.6).

Moteurs (cf. .claude/memory/reference_fal_ai_models.md → « Musique — Génération ») :
  - lyria3          : fal-ai/lyria3/pro                   — Google, dernier modèle, ~3 min (DÉFAUT)
  - lyria2          : fal-ai/lyria2                       — Google, instrumental tout style
  - cassette        : cassetteai/music-generator         — instrumental jusqu'à 3 min, le moins cher
  - ace-step        : fal-ai/ace-step                     — voix OU instrumental ([inst]), remix/extend
  - diffrhythm      : fal-ai/diffrhythm                   — chanson complète (chant) depuis paroles
  - minimax-music   : fal-ai/minimax-music               — compositions avec voix (max 60 s)
  - stable-audio-25 : fal-ai/stable-audio-25/text-to-audio— musique + SFX (Stable Audio 2.5)
  - elevenlabs      : fal-ai/elevenlabs/music            — qualité premium, sections (le plus cher)

⚠ Schémas d'entrée best-effort d'après les pages modèles fal.ai. À affiner avec une
vraie clé si un endpoint renvoie une erreur de paramètre (le mock ne dépend de rien).
"""

import os
import time

from PyQt6.QtCore import QThread, pyqtSignal
from core.config import load_config
from core.worker import humanize_api_error


# ── Catalogue ─────────────────────────────────────────────────────────────────
# kind          : forme des arguments (voir _build_args)
# vocals        : le moteur peut chanter des paroles
# lyrics        : un champ « paroles » est pertinent dans l'UI
# max_dur       : durée max raisonnable (s) pour le spinbox
# price         : indication tarifaire affichée
MUSIC_ENGINES = {
    "lyria3": {
        "label":    "Lyria 3 Pro (Google)  ·  dernier modèle · jusqu'à ~3 min  ·  ~$0.08/audio",
        "endpoint": "fal-ai/lyria3/pro",
        "kind":     "lyria",
        "vocals":   False,
        "lyrics":   False,
        "max_dur":  180,
        "price":    "~$0.08 / audio",
        "default":  True,
    },
    "lyria2": {
        "label":    "Lyria 2 (Google)  ·  instrumental tout style  ·  ~$0.10/30 s",
        "endpoint": "fal-ai/lyria2",
        "kind":     "lyria",
        "vocals":   False,
        "lyrics":   False,
        "max_dur":  60,
        "price":    "~$0.10 / 30 s",
    },
    "cassette": {
        "label":    "CassetteAI  ·  instrumental jusqu'à 3 min  ·  ~$0.02/min (éco)",
        "endpoint": "cassetteai/music-generator",
        "kind":     "cassette",
        "vocals":   False,
        "lyrics":   False,
        "max_dur":  180,
        "price":    "~$0.02 / min",
    },
    "ace-step": {
        "label":    "ACE-Step  ·  voix OU instrumental  ·  ~$0.012/min",
        "endpoint": "fal-ai/ace-step",
        "kind":     "ace",
        "vocals":   True,
        "lyrics":   True,
        "max_dur":  240,
        "price":    "~$0.012 / min",
    },
    "diffrhythm": {
        "label":    "DiffRhythm  ·  chanson complète (chant)  ·  ~$0.01/10 s",
        "endpoint": "fal-ai/diffrhythm",
        "kind":     "diffrhythm",
        "vocals":   True,
        "lyrics":   True,
        "max_dur":  285,
        "price":    "~$0.01 / 10 s",
    },
    "minimax-music": {
        "label":    "MiniMax Music  ·  compositions avec voix  ·  ~$0.035/gén.",
        "endpoint": "fal-ai/minimax-music",
        "kind":     "minimax",
        "vocals":   True,
        "lyrics":   True,
        "max_dur":  60,
        "price":    "~$0.035 / génération",
    },
    "stable-audio-25": {
        "label":    "Stable Audio 2.5  ·  musique + SFX  ·  ~$0.20/audio",
        "endpoint": "fal-ai/stable-audio-25/text-to-audio",
        "kind":     "stable",
        "vocals":   False,
        "lyrics":   False,
        "max_dur":  190,
        "price":    "~$0.20 / audio",
    },
    "elevenlabs": {
        "label":    "ElevenLabs Music  ·  qualité premium, sections  ·  ~$0.80/min",
        "endpoint": "fal-ai/elevenlabs/music",
        "kind":     "elevenlabs",
        "vocals":   True,
        "lyrics":   False,
        "max_dur":  300,
        "price":    "~$0.80 / min",
    },
}

# Ordre d'affichage dans le sélecteur (le défaut en tête).
ENGINE_ORDER = ["lyria3", "lyria2", "cassette", "ace-step", "diffrhythm",
                "minimax-music", "stable-audio-25", "elevenlabs"]


def default_engine() -> str:
    """Clé du moteur le plus performant proposé par défaut."""
    for k, spec in MUSIC_ENGINES.items():
        if spec.get("default"):
            return k
    return "lyria3"


def engine_spec(key: str) -> dict:
    return MUSIC_ENGINES.get(key, MUSIC_ENGINES[default_engine()])


def _music_output_dir() -> str:
    """Dossier de sortie des musiques générées (<projet>/data/music)."""
    try:
        from core.context import get_data_root
        d = os.path.join(get_data_root(), "music")
    except Exception:
        from core.pandora_dirs import get_bin_dir
        d = get_bin_dir("music")
    os.makedirs(d, exist_ok=True)
    return d


def _build_args(kind: str, prompt: str, lyrics: str, duration: float) -> dict:
    """Construit les arguments propres à chaque endpoint (best-effort)."""
    dur = max(1, int(round(duration)))
    if kind == "lyria":
        return {"prompt": prompt}
    if kind == "cassette":
        return {"prompt": prompt, "duration": dur}
    if kind == "ace":
        return {"tags": prompt, "lyrics": (lyrics.strip() or "[inst]"), "duration": dur}
    if kind == "diffrhythm":
        args = {"style_prompt": prompt}
        if lyrics.strip():
            args["lyrics"] = lyrics.strip()
        return args
    if kind == "minimax":
        args = {"prompt": prompt}
        if lyrics.strip():
            args["lyrics"] = lyrics.strip()
        return args
    if kind == "stable":
        return {"prompt": prompt, "seconds_total": dur}
    if kind == "elevenlabs":
        return {"prompt": prompt, "music_length_ms": dur * 1000}
    return {"prompt": prompt}


def _extract_audio_url(result) -> str:
    """Extrait l'URL audio d'une réponse fal.ai (formes variables selon moteur)."""
    if not isinstance(result, dict):
        raise RuntimeError(f"Réponse API inattendue : {str(result)[:200]}")
    for key in ("audio", "audio_file", "music", "output"):
        val = result.get(key)
        if isinstance(val, list) and val:
            first = val[0]
            url = (first.get("url", "") if isinstance(first, dict)
                   else first if isinstance(first, str) else "")
            if url:
                return url
        elif isinstance(val, dict) and val.get("url"):
            return val["url"]
        elif isinstance(val, str) and val:
            return val
    for key in ("url", "audio_url", "ref"):
        if result.get(key):
            return result[key]
    raise RuntimeError(f"URL audio manquante : {str(result)[:200]}")


class MusicWorker(QThread):
    """
    Génère un morceau de musique via le moteur fal.ai choisi.
    Sans clé fal.ai → mock (finished("") ). Avec clé → appel réel.
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)   # chemin du fichier audio (ou "" en mock)
    failed   = pyqtSignal(str)

    def __init__(self, engine_key: str, prompt: str, lyrics: str = "",
                 duration: float = 30.0, out_dir: str = ""):
        super().__init__()
        self._engine   = engine_key
        self._prompt   = (prompt or "").strip()
        self._lyrics   = lyrics or ""
        self._duration = float(duration)
        self._out_dir  = out_dir

    def run(self):
        key = load_config().get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        spec = engine_spec(self._engine)
        for pct, msg in [
            (15, f"{spec['label'].split('·')[0].strip()} (mode mock)…"),
            (55, "Composition de la musique…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]:
            self.progress.emit(pct, msg)
            time.sleep(0.35)
        self.finished.emit("")

    def _real(self, key: str):
        try:
            import fal_client
            import requests

            spec = engine_spec(self._engine)
            os.environ["FAL_KEY"] = key
            args = _build_args(spec["kind"], self._prompt, self._lyrics, self._duration)

            self.progress.emit(20, f"Envoi à fal.ai — {spec['label'].split('·')[0].strip()}…")
            result = fal_client.subscribe(spec["endpoint"], arguments=args)

            self.progress.emit(70, "Téléchargement du morceau…")
            url = _extract_audio_url(result)
            data = requests.get(url, timeout=300).content

            ext = ".mp3" if url.lower().split("?")[0].endswith(".mp3") else ".wav"
            out_dir = self._out_dir or _music_output_dir()
            os.makedirs(out_dir, exist_ok=True)
            safe = "".join(c for c in self._engine if c.isalnum() or c in "-_") or "music"
            path = os.path.join(out_dir, f"{safe}_{int(time.time())}{ext}")
            with open(path, "wb") as f:
                f.write(data)

            self.progress.emit(100, f"Musique générée ✓  ({spec['price']})")
            self.finished.emit(path)

        except Exception as e:
            self.failed.emit(humanize_api_error(f"Erreur musique : {e}"))
