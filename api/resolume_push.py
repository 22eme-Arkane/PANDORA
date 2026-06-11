"""
api/resolume_push.py — Envoi en file d'attente des clips PANDORA vers Resolume.

PushToResolumeWorker : pour chaque clip, charge le média dans le slot
[layer, colonne de départ + i] puis le renomme. Optionnel : règle le BPM de la
composition (depuis le set analysé du Conducteur) — PANDORA et Resolume parlent
alors le même tempo (beat-snap, autopilot…).

Signaux : progress(int, str) · finished(dict) · failed(str)
finished = {"sent": n, "failed": [noms], "layer": l, "first_column": c}
"""

import os

from PyQt6.QtCore import QThread, pyqtSignal

from resolume.client import ResolumeClient


class PushToResolumeWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    def __init__(self, clips: list, layer: int = 1, start_column: int = 1,
                 bpm: float = 0.0, host: str = "", port: int = 0,
                 client: ResolumeClient | None = None):
        """clips = [{"path": str, "name": str}] — name optionnel (nom du slot)."""
        super().__init__()
        self._clips  = [c for c in (clips or []) if c.get("path")]
        self._layer  = max(1, int(layer))
        self._start  = max(1, int(start_column))
        self._bpm    = float(bpm or 0)
        self._host   = host
        self._port   = port
        self._client = client   # injecté par les tests ; sinon créé dans run()

    def run(self):
        if not self._clips:
            self.failed.emit("Aucun clip à envoyer.")
            return
        try:
            client = self._client or ResolumeClient(self._host, self._port)
            self.progress.emit(2, "Connexion à Resolume…")
            info = client.get_product_info()
            if not info:
                self.failed.emit(f"Resolume injoignable — {client.last_error}")
                return
            self.progress.emit(6, f"Connecté à {info.get('name', 'Resolume')} ✓")

            if self._bpm > 0:
                if client.set_tempo(self._bpm):
                    self.progress.emit(8, f"Tempo composition : {self._bpm:g} BPM ✓")
                else:
                    # Non bloquant : les clips comptent plus que le tempo
                    self.progress.emit(8, f"⚠ Tempo non réglé — {client.last_error}")

            total, sent, failures = len(self._clips), 0, []
            for i, clip in enumerate(self._clips):
                if self.isInterruptionRequested():
                    return
                path = clip["path"]
                base = os.path.basename(path)
                col  = self._start + i
                pct  = 10 + int(85 * i / total)
                if not os.path.isfile(path):
                    failures.append(base)
                    self.progress.emit(pct, f"⚠ Introuvable : {base}")
                    continue
                self.progress.emit(pct, f"Slot L{self._layer}·C{col} ← {base}…")
                if client.load_clip(self._layer, col, path):
                    sent += 1
                    label = (clip.get("name") or "").strip()
                    if label:
                        client.set_clip_name(self._layer, col, label)
                        # le clip est chargé — un échec de renommage est cosmétique
                else:
                    failures.append(base)
                    self.progress.emit(pct, f"⚠ {base} : {client.last_error}")

            self.progress.emit(100, f"{sent}/{total} clip(s) dans Resolume ✓")
            self.finished.emit({
                "sent": sent, "failed": failures,
                "layer": self._layer, "first_column": self._start,
            })
        except Exception as e:
            self.failed.emit(f"Erreur inattendue : {e}")
