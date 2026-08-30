"""api/voice_audition.py — Génère l'extrait d'une voix, une seule fois.

fal ne publie pas d'extraits : entendre une voix suppose de la faire parler.
Ce worker fait dire à la voix choisie la phrase fixe de
`core.voice_auditions`, puis range le fichier dans le cache global.

Deux garanties qui rendent le bouton « Écouter » utilisable :

  - **Rien n'est régénéré.** Si l'extrait est déjà en cache, le worker rend la
    main immédiatement sans appeler fal — donc sans rien facturer. C'est ce qui
    permet de comparer les 113 voix d'Inworld sans y laisser un budget.
  - **Le mode mock reste muet plutôt que menteur.** Sans clé fal.ai, on
    n'invente pas un fichier audio : on le dit.
"""

import os
import time

from PyQt6.QtCore import QThread, pyqtSignal

from core.config import load_config
from core.speech_engines import build_args, spec, estimate_usd
from core.voice_auditions import AUDITION_TEXT_FR, audition_path, is_cached
from core.worker import humanize_api_error


class VoiceAuditionWorker(QThread):
    """Produit (ou retrouve) l'extrait d'un couple moteur/voix.

    `done(path, from_cache)` — chemin du fichier, et si l'extrait venait du
    cache (auquel cas l'appel n'a rien coûté).
    """

    progress = pyqtSignal(int, str)
    done     = pyqtSignal(str, bool)
    failed   = pyqtSignal(str)

    def __init__(self, engine: str, voice: str):
        super().__init__()
        self._engine = engine
        self._voice  = voice

    def run(self):
        try:
            path = audition_path(self._engine, self._voice)

            if is_cached(self._engine, self._voice):
                self.progress.emit(100, "Extrait déjà généré — lecture immédiate")
                self.done.emit(path, True)
                return

            key = load_config().get("api_key", "").strip()
            if not key:
                self.failed.emit(
                    "Aucune clé fal.ai : impossible de générer un extrait. "
                    "Renseignez la clé dans les Paramètres."
                )
                return

            self._generate(key, path)

        except Exception as e:
            self.failed.emit(humanize_api_error(f"Erreur extrait de voix : {e}"))

    def _generate(self, key: str, path: str):
        import fal_client
        import requests

        os.environ["FAL_KEY"] = key
        _est = estimate_usd(self._engine, len(AUDITION_TEXT_FR))
        _cost = f" (~${_est:.4f})" if _est else ""
        self.progress.emit(20, f"Génération de l'extrait — {self._voice}{_cost}…")

        args   = build_args(self._engine, AUDITION_TEXT_FR, voice=self._voice)
        result = fal_client.subscribe(spec(self._engine)["endpoint"], arguments=args)

        url = ""
        if isinstance(result, dict):
            audio = result.get("audio")
            if isinstance(audio, dict):
                url = audio.get("url", "")
            elif isinstance(audio, list) and audio:
                first = audio[0]
                url = (first.get("url", "") if isinstance(first, dict)
                       else first if isinstance(first, str) else "")
            elif isinstance(audio, str):
                url = audio
            if not url:
                url = result.get("audio_url", "") or result.get("url", "")
        if not url:
            raise RuntimeError(f"URL audio manquante : {str(result)[:200]}")

        self.progress.emit(70, "Téléchargement de l'extrait…")
        data = requests.get(url, timeout=180).content
        if not data:
            raise RuntimeError("Extrait vide reçu de fal.")

        # Écriture atomique : un fichier partiel laissé par une coupure serait
        # ensuite pris pour un extrait valable et jamais régénéré.
        tmp = f"{path}.part"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)

        self.progress.emit(100, "Extrait prêt ✓")
        self.done.emit(path, False)
