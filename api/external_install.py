"""api/external_install.py — Télécharger, installer, lancer un module externe.

Ce que PANDORA sait faire lui-même (core/externals), toujours dans un thread
et toujours après un clic explicite :

  ComfyUI    install → installeur officiel téléchargé puis lancé (l'utilisateur
                       suit son assistant) ;
             models  → les fichiers MiniMax H3 des gabarits officiels, déposés
                       dans le dossier de modèles de ComfyUI Desktop ;
             launch  → ouvre ComfyUI Desktop.
  H3 local   install → archive du projet communautaire dépliée dans le dossier
                       de modules de PANDORA, puis « setup.bat <palier> » dans une
                       console VISIBLE (téléchargement long, sortie utile) ;
             launch  → start_server.ps1 sans fenêtre, journal dans le dossier.
  Ollama     install → installeur officiel téléchargé puis lancé ;
             pull    → modèle téléchargé par l'API d'Ollama, progression suivie ;
             launch  → ouvre l'application Ollama.

Téléchargements REPRENABLES : un fichier `.part` interrompu reprend là où il
en était (en-tête Range — Hugging Face et GitHub l'acceptent) et n'est renommé
qu'une fois complet, pour que jamais un modèle tronqué ne passe pour présent.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import zipfile

from PyQt6.QtCore import QThread, pyqtSignal

from core import externals as _ex

_CHUNK = 1 << 20
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)


class Cancelled(Exception):
    pass


# ── Téléchargement ──────────────────────────────────────────────────────────

def remote_size(url: str, timeout: float = 20.0) -> int:
    """Taille annoncée (0 si inconnue) — suit les redirections."""
    import requests
    try:
        r = requests.head(url, allow_redirects=True, timeout=timeout)
        return int(r.headers.get("Content-Length") or r.headers.get("x-linked-size") or 0)
    except Exception:
        return 0


def download(url: str, dest: str, progress=None, is_cancelled=None,
             timeout: tuple = (20, 120)) -> str:
    """Télécharge `url` vers `dest`, en reprenant un `.part` existant.
    progress(done_bytes, total_bytes) ; is_cancelled() → True pour arrêter
    (le .part reste, la reprise suivante repartira de là)."""
    import requests
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    part = dest + ".part"
    have = os.path.getsize(part) if os.path.isfile(part) else 0
    headers = {"Range": f"bytes={have}-"} if have else {}
    r = requests.get(url, stream=True, headers=headers, timeout=timeout, allow_redirects=True)
    if have and r.status_code != 206:
        have = 0                                   # le serveur ignore Range : on repart
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code} sur {url}")
    length = int(r.headers.get("Content-Length") or 0)
    total = have + length if length else 0
    done = have
    with open(part, "ab" if have else "wb") as f:
        for chunk in r.iter_content(_CHUNK):
            if is_cancelled and is_cancelled():
                raise Cancelled()
            if chunk:
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    if total and done < total:
        raise RuntimeError(f"Téléchargement incomplet ({done}/{total} octets) : {os.path.basename(dest)}")
    os.replace(part, dest)
    return dest


def free_space(path: str) -> int:
    try:
        return shutil.disk_usage(path).free
    except Exception:
        return 0


def _human(n: float) -> str:
    return f"{n / 1e9:.1f} Go" if n >= 1e9 else f"{n / 1e6:.0f} Mo"


# ── Workers ─────────────────────────────────────────────────────────────────

class ExternalStatusWorker(QThread):
    """Sonde un ou plusieurs modules hors du thread de l'interface."""
    result = pyqtSignal(str, object)     # clé, core.externals.Status

    def __init__(self, keys, parent=None):
        super().__init__(parent)
        self._keys = list(keys)

    def run(self):
        for k in self._keys:
            try:
                st = _ex.detect(k)
            except Exception as e:
                st = _ex.Status(detail=f"Vérification impossible : {e}", checked=False)
            self.result.emit(k, st)


class ExternalInstallWorker(QThread):
    """Une action sur un module : install / models / pull / launch."""
    progress = pyqtSignal(int, str)
    done = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, key: str, action: str, params: dict | None = None, parent=None):
        super().__init__(parent)
        self.key, self.action, self.params = key, action, dict(params or {})
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def _is_cancelled(self) -> bool:
        return self._cancel or self.isInterruptionRequested()

    def run(self):
        try:
            handler = getattr(self, f"_{self.key}_{self.action}", None)
            if handler is None:
                raise RuntimeError(f"Action inconnue : {self.key}/{self.action}")
            out = handler() or {}
            if not self._is_cancelled():
                self.done.emit({"key": self.key, "action": self.action, **out})
        except Cancelled:
            self.failed.emit("Annulé — le téléchargement reprendra là où il s'est arrêté.")
        except Exception as e:
            self.failed.emit(str(e))

    # ── outils ──────────────────────────────────────────────────────────────

    def _fetch(self, url: str, dest: str, label: str, base_pct: int = 0, span: int = 100) -> str:
        def _p(done, total):
            if total:
                self.progress.emit(base_pct + int(span * done / total),
                                   f"{label} — {_human(done)} / {_human(total)}")
            else:
                self.progress.emit(base_pct, f"{label} — {_human(done)}")
        return download(url, dest, _p, self._is_cancelled)

    def _check_space(self, folder: str, needed: int):
        free = free_space(folder)
        if needed and free and free < needed * 1.05:
            raise RuntimeError(
                f"Espace disque insuffisant : {_human(needed)} nécessaires, {_human(free)} libres sur {folder}.")

    @staticmethod
    def _open(path: str):
        os.startfile(path)                                    # noqa: S606 — action voulue

    # ── ComfyUI ─────────────────────────────────────────────────────────────

    def _comfyui_install(self) -> dict:
        ext = _ex.EXTERNALS["comfyui"]
        dest = os.path.join(_ex.externals_dir(), "downloads", "Comfy Desktop Setup.exe")
        self.progress.emit(0, "Installeur ComfyUI Desktop…")
        self._fetch(ext.download_url, dest, "Installeur ComfyUI Desktop")
        self.progress.emit(100, "Installeur lancé — suivez son assistant.")
        self._open(dest)
        return {"launched": dest}

    def _comfyui_models(self) -> dict:
        md = _ex.comfy_models_dir()
        if not md:
            raise RuntimeError("Dossier de modèles de ComfyUI introuvable : lancez ComfyUI Desktop "
                               "une première fois (il crée ses dossiers), puis réessayez.")
        missing = _ex.h3_models_missing(md)
        if not missing:
            return {"downloaded": 0}
        sizes = [remote_size(m["url"]) for m in missing]
        self._check_space(md, sum(sizes))
        n = len(missing)
        for i, (m, sz) in enumerate(zip(missing, sizes)):
            dest = os.path.join(md, m["directory"], m["name"])
            base, span = int(100 * i / n), int(100 / n)
            self._fetch(m["url"], dest, f"{i + 1}/{n}  {m['name']}", base, span)
        self.progress.emit(100, "Modèles MiniMax H3 en place.")
        return {"downloaded": n, "dir": md}

    def _comfyui_launch(self) -> dict:
        exe = _ex.comfy_desktop_exe()
        if not exe:
            raise RuntimeError("ComfyUI Desktop introuvable.")
        self._open(exe)
        return {"launched": exe}

    # ── Ollama ──────────────────────────────────────────────────────────────

    def _ollama_install(self) -> dict:
        ext = _ex.EXTERNALS["ollama"]
        dest = os.path.join(_ex.externals_dir(), "downloads", "OllamaSetup.exe")
        self._fetch(ext.download_url, dest, "Installeur Ollama")
        self.progress.emit(100, "Installeur lancé — suivez son assistant.")
        self._open(dest)
        return {"launched": dest}

    def _ollama_pull(self) -> dict:
        import requests
        model = (self.params.get("model") or _ex.OLLAMA_DEFAULT_MODEL).strip()
        url = _ex._ollama_url() + "/api/pull"
        self.progress.emit(0, f"Ollama — téléchargement de « {model} »…")
        with requests.post(url, json={"name": model, "stream": True}, stream=True, timeout=(10, 600)) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if self._is_cancelled():
                    raise Cancelled()
                if not line:
                    continue
                try:
                    j = json.loads(line)
                except ValueError:
                    continue
                if j.get("error"):
                    raise RuntimeError(j["error"])
                tot, comp = j.get("total") or 0, j.get("completed") or 0
                if tot:
                    self.progress.emit(int(100 * comp / tot), f"{model} — {_human(comp)} / {_human(tot)}")
                else:
                    self.progress.emit(0, f"{model} — {j.get('status', '')}")
        self.progress.emit(100, f"Modèle « {model} » prêt.")
        return {"model": model}

    def _ollama_launch(self) -> dict:
        exe = _ex.ollama_exe()
        if not exe:
            raise RuntimeError("Ollama introuvable.")
        self._open(exe)
        return {"launched": exe}

    # ── MiniMax H3 local (sd.cpp) ───────────────────────────────────────────

    def _h3_local_install(self) -> dict:
        target = _ex.h3_local_dir()
        os.makedirs(target, exist_ok=True)
        self._check_space(target, int(_ex.H3_LOCAL_TIER_GB * 1e9))
        zip_path = os.path.join(_ex.externals_dir(), "downloads", "minimax-h3-local.zip")
        self._fetch(_ex.H3_LOCAL_ARCHIVE_URL, zip_path, "Scripts du projet", 0, 10)
        with zipfile.ZipFile(zip_path) as z:
            names = z.namelist()
            root = names[0].split("/")[0] if names and "/" in names[0] else ""
            for info in z.infolist():
                rel = info.filename[len(root) + 1:] if root and info.filename.startswith(root + "/") else info.filename
                if not rel or info.is_dir():
                    continue
                out = os.path.join(target, rel)
                os.makedirs(os.path.dirname(out), exist_ok=True)
                with z.open(info) as src, open(out, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        setup = os.path.join(target, "setup.bat")
        if not os.path.isfile(setup):
            raise RuntimeError("setup.bat absent de l'archive — le projet a changé de forme.")
        tier = self.params.get("tier") or _ex.H3_LOCAL_TIER
        # Console VISIBLE et qui reste ouverte (/k) : c'est l'installeur du
        # projet, long et bavard — l'utilisateur doit pouvoir le suivre.
        subprocess.Popen(["cmd.exe", "/k", f'"{setup}" {tier}'], cwd=target,
                         creationflags=_NEW_CONSOLE)
        self.progress.emit(100, f"setup.bat {tier} lancé dans une console (~{_ex.H3_LOCAL_TIER_GB} Go).")
        return {"dir": target, "tier": tier}

    def _h3_local_launch(self) -> dict:
        target = _ex.h3_local_dir()
        script = os.path.join(target, "start_server.ps1")
        if not os.path.isfile(script):
            raise RuntimeError("start_server.ps1 introuvable : installez d'abord le projet.")
        log = open(os.path.join(target, "pandora_server.log"), "ab")
        subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script],
                         cwd=target, stdout=log, stderr=subprocess.STDOUT, creationflags=_NO_WINDOW)
        # Le serveur charge ~25 Go : on lui laisse quelques secondes pour ouvrir le port.
        from core import h3_local as _h3l
        for _ in range(30):
            if self._is_cancelled():
                raise Cancelled()
            time.sleep(2)
            if _h3l.ping(_h3l.get_url())[0]:
                self.progress.emit(100, "Serveur MiniMax H3 local en marche.")
                return {"launched": script}
        self.progress.emit(100, "Serveur lancé — il charge encore ses modèles (journal : pandora_server.log).")
        return {"launched": script, "warming": True}
