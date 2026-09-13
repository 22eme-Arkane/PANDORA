"""api/comfy.py — Worker vidéo ComfyUI : un workflow, des valeurs, un fichier.

Même contrat que les workers fal (`progress`, `finished(dict)`, `failed`) pour
que l'onglet Moteurs, la Vidéothèque et le journal de coût n'aient rien à
savoir de ComfyUI.

Déroulé :
  1. trouver un serveur vivant (adresse réglée, sinon 8188 puis 8000) ;
  2. charger le workflow (gabarit PANDORA ou fichier de l'utilisateur), le
     convertir au format API avec `/object_info`, remplir les entrées connues ;
  3. déposer l'image de départ / de fin par `/upload/image` si le mode le veut ;
  4. `POST /prompt`, puis `/history/{id}` toutes les deux secondes jusqu'au
     résultat — l'annulation coupe le suivi ET demande l'interruption au serveur ;
  5. `/view` pour rapatrier le fichier, WebM → MP4 si besoin (ffmpeg embarqué).

Coût : 0 $. `core/pricing` porte l'entrée `comfy` à zéro pour que le journal ne
retombe pas sur le tarif d'un moteur inconnu.
"""

from __future__ import annotations

import os
import time

from PyQt6.QtCore import pyqtSignal

from core import comfy as _cf
from core import comfy_workflow as _wf
from api.video_engines import _CancellableWorker, _video_output_dir, engine_prompt
from core.worker import humanize_api_error

MODEL = "comfy"
_POLL_S = 2.0
_MAX_WAIT_S = 4 * 3600


class ComfyWorker(_CancellableWorker):
    """params attendus (tous optionnels sauf prompt) :
        prompt, mode ("t2v"|"i2v"), image_path, end_image_path,
        workflow_path  — fichier .json (format éditeur OU API),
        fill           — liste de (classe, entrée, valeur) appliquée après les
                         remplissages standard,
        resolution, aspect_ratio, duration, seed,
        engine_label   — nom affiché dans les messages.
    """

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    def __init__(self, params: dict):
        super().__init__()
        self.params = params
        self._label = params.get("engine_label") or "ComfyUI"

    # ── Étapes ───────────────────────────────────────────────────────────────

    def _upload(self, base: str, path: str) -> str:
        """Dépose une image d'entrée ; rend le nom que les nœuds LoadImage
        attendent (`subfolder/filename` ou `filename`)."""
        import requests
        with open(path, "rb") as f:
            r = requests.post(f"{base}/upload/image",
                              files={"image": (os.path.basename(path), f)},
                              data={"overwrite": "true", "subfolder": "pandora"},
                              timeout=120)
        r.raise_for_status()
        j = r.json() or {}
        name = j.get("name") or os.path.basename(path)
        sub = j.get("subfolder") or ""
        return f"{sub}/{name}" if sub else name

    def _load_and_fill(self, base: str) -> dict:
        from core import comfy_h3 as _h3c
        path = self.params.get("workflow_path") or ""
        if not path or not os.path.isfile(path):
            raise ValueError("Aucun workflow ComfyUI : choisissez un gabarit H3 ou un fichier .json.")
        wf = _wf.load(path)
        info = _cf.fetch_object_info(base)
        api = _wf.to_api(wf, info)

        # Remplissages standard, par convention de classe (voir core/comfy_h3).
        # fill_plan lève NoPromptTarget si aucun nœud ne peut recevoir le
        # texte : envoyer le gabarit tel quel rendrait la vidéo de l'exemple.
        prompt_en = engine_prompt(self.params)
        plan = _h3c.fill_plan(api, self.params, prompt_en)
        _wf.fill(api, plan)
        _h3c.apply_images(api, self.params)
        for ctype, name, value in (self.params.get("fill") or []):
            _wf.fill(api, [(ctype, name, value)])
        return api

    # ── Exécution ────────────────────────────────────────────────────────────

    def run(self):
        try:
            import requests

            base = _cf.discover()
            if not base:
                raise RuntimeError(
                    "ComfyUI injoignable. Lancez ComfyUI Desktop (ou corrigez "
                    "l'adresse dans Paramètres), puis relancez.")

            self.progress.emit(6, f"{self._label} — lecture du workflow…")
            # Images d'entrée : déposées AVANT le remplissage, pour que les
            # nœuds LoadImage reçoivent le nom côté serveur.
            for key, pkey in (("image_path", "_comfy_image"), ("end_image_path", "_comfy_end_image")):
                p = self.params.get(key) or ""
                if p and os.path.isfile(p):
                    self.progress.emit(10, f"{self._label} — envoi de l'image…")
                    self.params[pkey] = self._upload(base, p)

            api = self._load_and_fill(base)

            self.progress.emit(15, f"{self._label} — envoi à ComfyUI…")
            client_id = _cf.new_client_id()
            r = requests.post(f"{base}/prompt", json=_cf.prompt_payload(api, client_id), timeout=60)
            if r.status_code >= 400:
                # ComfyUI explique les erreurs de validation nœud par nœud.
                try:
                    j = r.json()
                    err = j.get("error", {}).get("message") or ""
                    nodes = j.get("node_errors") or {}
                    det = "; ".join(f"{k}: {v.get('errors', [{}])[0].get('message', '')}"
                                    for k, v in list(nodes.items())[:3] if isinstance(v, dict))
                    raise RuntimeError(f"ComfyUI a refusé le workflow — {err} {det}".strip())
                except ValueError:
                    r.raise_for_status()
            pid = (r.json() or {}).get("prompt_id")
            if not pid:
                raise RuntimeError(f"ComfyUI n'a pas rendu d'identifiant : {r.text[:200]}")

            t0 = time.time()
            entry = None
            while True:
                if self._cancelled or self.isInterruptionRequested():
                    try:
                        requests.post(f"{base}/interrupt", timeout=5)
                        requests.post(f"{base}/queue", json={"delete": [pid]}, timeout=5)
                    except Exception:
                        pass
                    return
                if time.time() - t0 > _MAX_WAIT_S:
                    raise RuntimeError("Délai dépassé : ComfyUI ne répond plus.")
                h = requests.get(f"{base}/history/{pid}", timeout=30).json() or {}
                entry = h.get(pid)
                if entry:
                    state, msg = _cf.history_status(entry)
                    if state == "success":
                        break
                    if state == "error":
                        raise RuntimeError(f"Échec côté ComfyUI : {msg}")
                elapsed = int(time.time() - t0)
                pos = ""
                try:
                    q = requests.get(f"{base}/queue", timeout=10).json() or {}
                    pending = [x for x in (q.get("queue_pending") or []) if len(x) > 1 and x[1] == pid]
                    if pending:
                        pos = f" · en file ({len(q.get('queue_pending') or [])})"
                except Exception:
                    pass
                self.progress.emit(15 + min(70, elapsed // 6),
                                   f"{self._label} — rendu en cours ({elapsed} s){pos}…")
                time.sleep(_POLL_S)

            files = _cf.outputs_of(entry)
            if not files:
                raise RuntimeError("Le workflow s'est terminé sans produire de fichier de sortie.")
            item = files[0]
            self.progress.emit(90, f"{self._label} — rapatriement de {item['filename']}…")
            data = requests.get(_cf.view_url(base, item), timeout=600).content

            out_dir = _video_output_dir()
            ext = os.path.splitext(item["filename"])[1].lower() or ".mp4"
            mode = "i2v" if self.params.get("image_path") else "t2v"
            local = os.path.join(out_dir, f"{MODEL}_{mode}_{int(time.time())}{ext}")
            with open(local, "wb") as f:
                f.write(data)
            if ext in (".webm", ".gif", ".webp"):
                from api.h3_local import _to_mp4
                local = _to_mp4(local)

            self.progress.emit(100, f"{self._label} ✓  0 $")
            if not self._cancelled:
                self.finished.emit({
                    "url":          "",
                    "local_path":   local,
                    "duration":     self.params.get("duration") or 0,
                    "resolution":   self.params.get("resolution") or "",
                    "model":        f"{MODEL}-{mode}",
                    "credits_used": 0.0,
                })
        except Exception as e:
            if not self._cancelled:
                self.failed.emit(humanize_api_error(f"Erreur {self._label} : {e}"))
