"""
Client du pont DaVinci Resolve (TCP 127.0.0.1:19876).

Le pont (davinci/bridge_server.py, installé sous le nom seedance_bridge.py) doit
tourner DANS Resolve : Espace de travail → Scripts → seedance_bridge.

Version 2 (04/10/2026) — fin des pannes silencieuses relevées par l'audit :
  • l'erreur renvoyée par le pont remonte (« Aucun projet ouvert », délai,
    fichier introuvable…) au lieu de finir en « ✓ sauvegardé » ;
  • le client attend toujours plus longtemps que le pont (3 s < 6 s en v1 :
    un import réussi après coup était déclaré raté) ;
  • un pont d'avant le versionnage (réponse « pong ») est reconnu comme
    PÉRIMÉ : il faut mettre les scripts à jour et le relancer ;
  • `is_connected()` ne refait un ping qu'au-delà de 2 s (l'interface en
    faisait trois par rafraîchissement, sur son propre thread).
Aucune dépendance Qt : appelable depuis un QThread comme depuis un test.
"""

import json
import os
import socket
import threading
import time

HOST = "127.0.0.1"
PORT = 19876

# Version du pont livrée avec CETTE version de PANDORA (davinci/bridge_server.py).
EXPECTED_BRIDGE = 2

PING_TIMEOUT = 2.0
# Sous Windows, une connexion locale vers un port SANS écoute n'est pas refusée
# tout de suite : la pile TCP réessaie ~2 s (mesuré le 04/10/2026). Un pont
# vivant accepte en quelques millisecondes : au-delà d'une seconde de
# connexion, il ne tourne pas.
CONNECT_TIMEOUT = 1.0
CALL_TIMEOUT = 12.0      # > attente du pont pour une commande courte (8 s)
LONG_TIMEOUT = 190.0     # > attente du pont pour un montage / import en lot (180 s)
CACHE_SECONDS = 2.0

# Messages (traduits par l'interface via core.i18n.translate).
ERR_NOT_RUNNING = "Le pont PANDORA ne tourne pas dans DaVinci Resolve."
ERR_TIMEOUT = "Le pont DaVinci ne répond pas (Resolve occupé, ou fenêtre du pont fermée)."
ERR_NO_ANSWER = "Le pont DaVinci a coupé la connexion sans répondre."
ERR_BAD_ANSWER = "Réponse illisible du pont DaVinci."
ERR_OUTDATED = "Le pont lancé dans DaVinci Resolve est une ancienne version."
ERR_REFUSED = "Import refusé par DaVinci Resolve."

HELP_NOT_RUNNING = (
    "1. Ouvrez DaVinci Resolve et un projet.\n"
    "2. Espace de travail → Scripts → seedance_bridge (laissez sa petite fenêtre ouverte).\n"
    "3. Revenez ici et cliquez sur « Connecter ».\n\n"
    "Le script n'est pas dans le menu ? Paramètres → DaVinci Resolve → "
    "« Installer / mettre à jour les scripts », puis redémarrez Resolve."
)
HELP_OUTDATED = (
    "1. Paramètres → DaVinci Resolve → « Installer / mettre à jour les scripts ».\n"
    "2. Fermez la fenêtre « PANDORA Bridge » dans Resolve (ou redémarrez Resolve).\n"
    "3. Relancez Espace de travail → Scripts → seedance_bridge."
)
HELP_API = (
    "Le pont tourne, mais l'API de DaVinci Resolve ne répond pas. Relancez "
    "seedance_bridge depuis Espace de travail → Scripts, avec un projet ouvert. "
    "Depuis Resolve 21.1, le scripting est réservé à DaVinci Resolve Studio."
)


def translated(text: str) -> str:
    """Traduit un message du pont paragraphe par paragraphe : les phrases fixes
    sont dans core.i18n, un détail technique (chemin, erreur Resolve) reste tel quel."""
    try:
        from core.i18n import translate
    except Exception:
        return text or ""
    return "\n\n".join(translate(p) for p in (text or "").split("\n\n"))


# ── Transport ─────────────────────────────────────────────────────────────────

def call(cmd: str, params: dict | None = None,
         timeout: float = CALL_TIMEOUT) -> tuple[bool, object, str]:
    """Envoie une commande au pont. → (ok, résultat, message d'erreur)."""
    request = json.dumps({"cmd": cmd, "params": params or {}}, ensure_ascii=False) + "\n"
    try:
        sock = socket.create_connection((HOST, PORT),
                                        timeout=min(timeout, CONNECT_TIMEOUT))
    except OSError:                        # refusé, ou rien n'écoute (cf. CONNECT_TIMEOUT)
        return False, None, ERR_NOT_RUNNING
    data = b""
    with sock:
        try:
            sock.settimeout(timeout)
            sock.sendall(request.encode("utf-8"))
            while not data.endswith(b"\n"):
                chunk = sock.recv(65536)
                if not chunk:
                    break
                data += chunk
        except (TimeoutError, socket.timeout):
            return False, None, ERR_TIMEOUT
        except OSError:
            return False, None, ERR_NO_ANSWER
    if not data:
        return False, None, ERR_NO_ANSWER
    try:
        response = json.loads(data.decode("utf-8"))
    except ValueError:
        return False, None, ERR_BAD_ANSWER
    if response.get("ok"):
        return True, response.get("result"), ""
    return False, response.get("result"), str(response.get("error") or ERR_BAD_ANSWER)


def _send(cmd: str, params: dict | None = None) -> tuple[bool, object]:
    """Compatibilité : (ok, résultat) sans le message d'erreur."""
    ok, result, _err = call(cmd, params)
    return ok, result


# ── Installation des scripts (compatibilité — voir davinci/scripts_install) ───

def install_bridge_server() -> tuple[bool, str]:
    from davinci import scripts_install
    res = scripts_install.install()
    return bool(res["ok"]), "\n".join(res["written"]) or "; ".join(e for _d, e in res["failed"])


def install_pandora_send() -> tuple[bool, str]:
    return install_bridge_server()


# ── Connexion (singleton `resolve`) ───────────────────────────────────────────

class DaVinciConnection:
    """État de la connexion au pont, partagé par toute l'application.
    Usage : from davinci.bridge import resolve"""

    def __init__(self):
        self._lock = threading.Lock()
        self._connected = False
        self._checked_at = 0.0
        self.info: dict = {}          # dernière réponse du ping (pont v2)
        self.project = ""
        self.timeline = ""
        self.last_error = ""

    # ── État ──────────────────────────────────────────────────────────────────

    @property
    def bridge_version(self) -> int:
        """0 = inconnu, 1 = pont d'avant le versionnage, 2+ = pont versionné."""
        try:
            return int(self.info.get("bridge") or 0)
        except (TypeError, ValueError):
            return 0

    @property
    def outdated(self) -> bool:
        return self._connected and 0 < self.bridge_version < EXPECTED_BRIDGE

    @property
    def api_ok(self) -> bool:
        return bool(self.info.get("api_ok"))

    @property
    def product_label(self) -> str:
        return " ".join(x for x in (str(self.info.get("product") or ""),
                                    str(self.info.get("version") or "")) if x)

    def ping(self, timeout: float = PING_TIMEOUT) -> bool:
        ok, result, err = call("ping", timeout=timeout)
        if ok and result == "pong":                      # pont version 1
            info = {"bridge": 1, "api_ok": None}
        elif ok and isinstance(result, dict) and result.get("pong"):
            info = dict(result)
        else:
            info = None
            err = err or ERR_BAD_ANSWER
        with self._lock:
            self._checked_at = time.monotonic()
            if info is None:
                self._connected = False
                self.info = {}
                self.last_error = err
                return False
            self._connected = True
            self.info = info
            self.last_error = ""
            return True

    def fetch_status(self) -> dict:
        """Projet et timeline ouverts (mis en cache pour l'interface)."""
        if self.bridge_version >= 2:
            ok, result, err = call("status")
            if ok and isinstance(result, dict):
                self.project = str(result.get("project") or "")
                self.timeline = str(result.get("timeline") or "")
            else:
                self.project = self.timeline = ""
                if err:
                    self.last_error = err
        else:
            _ok, proj, _e = call("get_project_name")
            _ok, tl, _e = call("get_timeline_name")
            self.project, self.timeline = str(proj or ""), str(tl or "")
        return {"project": self.project, "timeline": self.timeline}

    def connect(self) -> tuple[bool, str]:
        """Ping + état du projet. → (connecté, message d'aide si problème)."""
        if not self.ping():
            return False, self.explain()
        if self.bridge_version < 2:
            # Le pont v1 ne dit pas si l'API répond : on le lui demande.
            _ok, dvr_err, _e = call("get_dvr_error")
            self.info["api_ok"] = not dvr_err
            self.info["error"] = str(dvr_err or "")
        self.fetch_status()
        return True, ("" if self.api_ok and not self.outdated else self.explain())

    def explain(self) -> str:
        """Message d'aide (français, à traduire) décrivant l'état courant."""
        if not self._connected:
            return (self.last_error or ERR_NOT_RUNNING) + "\n\n" + HELP_NOT_RUNNING
        if self.outdated:
            return ERR_OUTDATED + "\n\n" + HELP_OUTDATED
        if not self.api_ok:
            detail = str(self.info.get("error") or "")
            return HELP_API + (("\n\n" + detail) if detail else "")
        return ""

    def is_connected(self, max_age: float = CACHE_SECONDS) -> bool:
        if not self._connected:
            return False
        if time.monotonic() - self._checked_at < max_age:
            return True
        return self.ping()

    def disconnect(self):
        with self._lock:
            self._connected = False
            self.info = {}

    def refresh(self):
        self._checked_at = 0.0

    def _note_failure(self, err: str):
        self.last_error = err
        if err in (ERR_NOT_RUNNING, ERR_NO_ANSWER):
            with self._lock:
                self._connected = False

    def get_dvr_error(self) -> str:
        if self.bridge_version >= 2:
            return "" if self.api_ok else str(self.info.get("error") or "")
        _ok, err, _e = call("get_dvr_error")
        return str(err or "")

    # ── Infos projet (compatibilité) ──────────────────────────────────────────

    def project_name(self) -> str:
        return self.fetch_status()["project"]

    def timeline_name(self) -> str:
        return self.fetch_status()["timeline"]

    # ── Actions ───────────────────────────────────────────────────────────────

    def import_clip(self, file_path: str, sub_bin: str = "", meta: dict | None = None,
                    color: str = "") -> tuple[bool, str]:
        """Importe un fichier dans PANDORA[/sous-chutier]. → (ok, erreur)."""
        params = {"path": os.path.normpath(file_path), "sub_bin": sub_bin or ""}
        if self.bridge_version >= 2:
            if meta:
                params["meta"] = meta
            if color:
                params["color"] = color
        ok, result, err = call("import_to_pandora_bin", params)
        if ok and result:
            self.last_error = ""
            return True, ""
        err = err or ERR_REFUSED
        self._note_failure(err)
        return False, err

    def import_media_to_bin(self, file_path: str, sub_bin: str = "",
                            meta: dict | None = None, color: str = "") -> bool:
        return self.import_clip(file_path, sub_bin, meta, color)[0]

    def import_media(self, file_path: str) -> bool:
        ok, result, err = call("import_media", {"path": os.path.normpath(file_path)})
        if not (ok and result):
            self._note_failure(err or ERR_REFUSED)
        return ok and bool(result)

    def build_timeline(self, name: str, clips: list[dict]) -> tuple[bool, object]:
        """Monte `clips` dans l'ordre sur une nouvelle timeline.
        → (True, {timeline, count, reused, missing, errors}) ou (False, erreur)."""
        if not self.ping():
            return False, self.explain()
        if self.bridge_version < 2:
            return False, ERR_OUTDATED + "\n\n" + HELP_OUTDATED
        ok, result, err = call("build_timeline", {"name": name, "clips": clips},
                               timeout=LONG_TIMEOUT)
        if ok and isinstance(result, dict):
            return True, result
        self._note_failure(err or ERR_BAD_ANSWER)
        return False, err or ERR_BAD_ANSWER

    def create_pandora_bins(self, bin_names: list) -> tuple[bool, str]:
        ok, result, err = call("create_pandora_bins", {"bins": bin_names})
        if ok and isinstance(result, dict):
            n = result.get("total", len(bin_names))
            return True, f"{n} sous-dossier(s) créé(s) dans le Media Pool (bin PANDORA)"
        return False, err or ERR_BAD_ANSWER

    def get_selected_clip_info(self) -> dict:
        _ok, info, _e = call("get_selected_clip")
        return info if isinstance(info, dict) else {}

    def get_timeline_clips(self) -> list:
        """Clips vidéo de la timeline active (toutes les pistes avec un pont v2)."""
        _ok, clips, _e = call("get_timeline_clips")
        return clips if isinstance(clips, list) else []

    # ── Compatibilité avec l'ancien code ──────────────────────────────────────

    def get_media_pool(self):
        return None

    def get_current_timeline(self):
        return None


resolve = DaVinciConnection()
