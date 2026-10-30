"""core/local_files.py — Une URL http://127.0.0.1 pour un fichier de ce PC.

Les points de génération de PANDORA téléchargent le résultat d'un moteur par
`requests.get(url)` : une URL fal, ou l'URL `/view` du ComfyUI de ce PC. Un
gabarit calculé par AIODOS (core/comfy_aiodos), lui, arrive DÉJÀ sur le disque.
Plutôt que de retoucher la trentaine de points qui téléchargent, ce module
sert ce fichier-là sous une URL locale, téléchargeable exactement comme les
autres :

    url = url_for(r"C:\\…\\mood_1.png")   # http://127.0.0.1:<port>/f/<jeton>/mood_1.png

  · seulement sur 127.0.0.1 (jamais une autre interface : PANDORA ne doit pas
    devenir un relais ouvert vers les fichiers de l'utilisateur) ;
  · seuls les fichiers DÉCLARÉS ici sont servis, chacun sous un jeton tiré au
    hasard : ni liste, ni chemin ;
  · le serveur ne démarre qu'au premier fichier déclaré ; il vit le temps de
    PANDORA (fil démon).
"""

from __future__ import annotations

import http.server
import mimetypes
import os
import secrets
import threading
from collections import OrderedDict
from urllib.parse import quote, unquote, urlsplit

HOST = "127.0.0.1"
PREFIX = "/f/"
#: Les fichiers déclarés gardés au plus (les plus anciens sont oubliés) : de
#: quoi couvrir une longue session de lots sans grossir sans fin.
MAX_FILES = 2000
_BLOCK = 1024 * 1024

_lock = threading.Lock()
_files: "OrderedDict[str, str]" = OrderedDict()      # jeton → chemin
_server = None


class _Handler(http.server.BaseHTTPRequestHandler):
    server_version = "PANDORA"

    def log_message(self, format, *args):      # pas de journal sur la console
        pass

    def _found(self):
        path = unquote(urlsplit(self.path).path)
        if not path.startswith(PREFIX):
            return None
        token = path[len(PREFIX):].split("/", 1)[0]
        with _lock:
            local = _files.get(token)
        return local if local and os.path.isfile(local) else None

    def do_HEAD(self):
        self._serve(body=False)

    def do_GET(self):
        self._serve(body=True)

    def _serve(self, body: bool):
        local = self._found()
        if local is None:
            self.send_error(404)
            return
        try:
            size = os.path.getsize(local)
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(local)[0]
                             or "application/octet-stream")
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if body:
                with open(local, "rb") as f:
                    for block in iter(lambda: f.read(_BLOCK), b""):
                        self.wfile.write(block)
        except (BrokenPipeError, ConnectionResetError):
            pass


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):     # un client parti n'est pas une erreur
        pass


def _ensure_server():
    global _server
    if _server is None:
        server = _Server((HOST, 0), _Handler)
        threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.25},
                         name="pandora-local-files", daemon=True).start()
        _server = server
    return _server


def url_for(path: str) -> str:
    """L'URL locale qui sert ce fichier (déclaré ici jusqu'à la fin de PANDORA)."""
    local = os.path.abspath(str(path))
    if not os.path.isfile(local):
        raise FileNotFoundError(local)
    token = secrets.token_urlsafe(18)
    with _lock:
        server = _ensure_server()
        _files[token] = local
        while len(_files) > MAX_FILES:
            _files.popitem(last=False)
    port = server.server_address[1]
    return f"http://{HOST}:{port}{PREFIX}{token}/{quote(os.path.basename(local))}"


def path_of(url: str) -> str | None:
    """Le chemin d'un fichier servi ici (None pour toute autre URL) : un appelant
    qui le sait peut le lire directement, sans passer par HTTP."""
    try:
        parts = urlsplit(str(url or ""))
    except ValueError:
        return None
    server = _server
    if server is None or parts.hostname != HOST or parts.port != server.server_address[1]:
        return None
    path = unquote(parts.path)
    if not path.startswith(PREFIX):
        return None
    with _lock:
        return _files.get(path[len(PREFIX):].split("/", 1)[0])


def forget(url: str) -> None:
    """Ne plus servir ce fichier."""
    parts = urlsplit(str(url or ""))
    path = unquote(parts.path)
    if path.startswith(PREFIX):
        with _lock:
            _files.pop(path[len(PREFIX):].split("/", 1)[0], None)


def shutdown() -> None:
    """Arrête le serveur et oublie tous les fichiers (fin des harnais) ; il
    redémarre de lui-même au prochain `url_for`."""
    global _server
    with _lock:
        server, _server = _server, None
        _files.clear()
    if server is not None:
        server.shutdown()
        server.server_close()
