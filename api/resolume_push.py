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
                 show_mode: bool = False,
                 client: ResolumeClient | None = None):
        """clips = [{"path": str, "name": str}] — name optionnel (nom du slot).
        show_mode : chaque clip est réglé « Play Once & Hold » + Beat Snap 1 mesure
        + Autopilot « next clip » → la séquence s'enchaîne seule, calée au tempo."""
        super().__init__()
        self._clips  = [c for c in (clips or []) if c.get("path")]
        self._layer  = max(1, int(layer))
        self._start  = max(1, int(start_column))
        self._bpm    = float(bpm or 0)
        self._host   = host
        self._port   = port
        self._show   = bool(show_mode)
        self._client = client   # injecté par les tests ; sinon créé dans run()

    def _apply_show_mode(self, client: ResolumeClient, col: int,
                         layer: int = 0) -> bool:
        """Patch tolérant du clip chargé (voir resolume.client.set_choice_param)."""
        from resolume.client import set_choice_param, find_subtree
        layer = layer or self._layer
        clip = client.get_clip(layer, col)
        if not clip:
            return False
        patched = False
        patched |= set_choice_param(clip, {"playmode"}, "hold")
        patched |= set_choice_param(clip, {"beatsnap"}, "bar")
        ap = find_subtree(clip, "autopilot")
        if ap is not None:
            patched |= set_choice_param(ap, {"target", "action"}, "next")
        return bool(patched) and client.put_clip(layer, col, clip)

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

            # Cibles par clip : couche/colonne explicites ({"layer","column"})
            # sinon couche commune + colonnes consécutives
            _targets = []
            _auto_col = {}
            for clip in self._clips:
                lay = int(clip.get("layer", self._layer) or self._layer)
                if "column" in clip:
                    col = int(clip["column"])
                else:
                    col = _auto_col.get(lay, self._start)
                _auto_col[lay] = col + 1
                _targets.append((lay, col))

            # La composition doit avoir assez de COLONNES (vu en réel : 9 colonnes
            # pour 27 clips → 18 échecs). On l'étend automatiquement.
            _layers, _cols = client.composition_counts()
            needed = max((c for _, c in _targets), default=self._start)
            if _cols and needed > _cols:
                self.progress.emit(9, f"Ajout de {needed - _cols} colonne(s)…")
                added = 0
                for _ in range(needed - _cols):
                    if not client.add_column():
                        break
                    added += 1
                if added < needed - _cols:
                    self.progress.emit(
                        9, f"⚠ {added} colonne(s) ajoutée(s) seulement — {client.last_error}")

            total, sent, failures = len(self._clips), 0, []
            for i, clip in enumerate(self._clips):
                if self.isInterruptionRequested():
                    return
                path = clip["path"]
                base = os.path.basename(path)
                lay, col = _targets[i]
                pct  = 10 + int(85 * i / total)
                if not os.path.isfile(path):
                    failures.append(base)
                    self.progress.emit(pct, f"⚠ Introuvable : {base}")
                    continue
                self.progress.emit(pct, f"Slot L{lay}·C{col} ← {base}…")
                if client.load_clip(lay, col, path):
                    sent += 1
                    label = (clip.get("name") or "").strip()
                    if label:
                        client.set_clip_name(lay, col, label)
                        # le clip est chargé — un échec de renommage est cosmétique
                    if self._show and not self._apply_show_mode(client, col, lay):
                        self.progress.emit(pct, f"⚠ Mode show non appliqué sur {base}")
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
