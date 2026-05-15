"""
Connexion au bridge server DaVinci Resolve via TCP localhost:19876.

Le bridge server (davinci/bridge_server.py) doit tourner DANS DaVinci :
    Espace de travail → Scripts → seedance_bridge
"""

import json
import os
import shutil
import socket
import sys

HOST    = "127.0.0.1"
PORT    = 19876
TIMEOUT = 3.0

# Dossier Scripts DaVinci (Windows)
_SCRIPTS_DIRS = [
    r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Fusion\Scripts\Utility",
    os.path.join(os.path.expanduser("~"), "AppData", "Roaming",
                 "Blackmagic Design", "DaVinci Resolve", "Support",
                 "Fusion", "Scripts", "Utility"),
]


# ── Transport TCP ─────────────────────────────────────────────────────────────

def _send(cmd: str, params: dict | None = None) -> tuple[bool, object]:
    """Envoie une commande JSON au bridge server. Retourne (ok, result)."""
    try:
        req = json.dumps({"cmd": cmd, "params": params or {}}) + "\n"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(TIMEOUT)
            s.connect((HOST, PORT))
            s.sendall(req.encode("utf-8"))
            data = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
                if data.endswith(b"\n"):
                    break
        resp = json.loads(data.decode("utf-8"))
        return resp.get("ok", False), resp.get("result")
    except (ConnectionRefusedError, TimeoutError, OSError):
        return False, None
    except Exception as e:
        return False, None


# ── Installation du bridge server ─────────────────────────────────────────────

def install_bridge_server() -> tuple[bool, str]:
    """
    Copie bridge_server.py dans le dossier Scripts de DaVinci Resolve.
    Retourne (succès, chemin_installé_ou_erreur).
    """
    if getattr(sys, "frozen", False):
        src = os.path.join(sys._MEIPASS, "davinci", "bridge_server.py")
    else:
        src = os.path.join(os.path.dirname(__file__), "bridge_server.py")
    if not os.path.isfile(src):
        return False, f"bridge_server.py introuvable : {src}"
    for dest_dir in _SCRIPTS_DIRS:
        try:
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, "seedance_bridge.py")
            shutil.copy2(src, dest)
            return True, dest
        except Exception:
            continue
    return False, "Impossible d'écrire dans les dossiers Scripts DaVinci."


# ── Connexion singleton ───────────────────────────────────────────────────────

class DaVinciConnection:
    """
    Interface vers DaVinci Resolve via le bridge server TCP.
    Usage : from davinci.bridge import resolve
    """

    def __init__(self):
        self._connected = False

    def connect(self) -> tuple[bool, str]:
        ok, result = _send("ping")
        if ok and result == "pong":
            self._connected = True
            return True, ""
        return False, (
            "Bridge Seedance non démarré dans DaVinci.\n\n"
            "Étapes :\n"
            "1. Clique « Installer le bridge » ci-dessous\n"
            "2. Dans DaVinci : Espace de travail → Scripts → seedance_bridge\n"
            "3. Reviens ici et clique Connecter"
        )

    def is_connected(self) -> bool:
        if not self._connected:
            return False
        ok, _ = _send("ping")
        if not ok:
            self._connected = False
        return ok

    def disconnect(self):
        self._connected = False

    def refresh(self):
        pass

    def get_dvr_error(self) -> str:
        """Récupère le message d'erreur DaVinci depuis le bridge server."""
        _, err = _send("get_dvr_error")
        return err or ""

    # ── Infos projet ──────────────────────────────────────────────────────────

    def project_name(self) -> str:
        _, name = _send("get_project_name")
        return name or ""

    def timeline_name(self) -> str:
        _, name = _send("get_timeline_name")
        return name or ""

    # ── Actions ───────────────────────────────────────────────────────────────

    def import_media(self, file_path: str) -> bool:
        ok, result = _send("import_media", {"path": os.path.normpath(file_path)})
        return ok and bool(result)

    def create_pandora_bins(self, bin_names: list) -> tuple[bool, str]:
        """Crée le bin PANDORA et ses sous-bins dans le Media Pool DaVinci."""
        ok, result = _send("create_pandora_bins", {"bins": bin_names})
        if ok and isinstance(result, dict):
            n = result.get("total", len(bin_names))
            return True, f"{n} sous-dossier(s) créé(s) dans le Media Pool (bin PANDORA)"
        return False, "Création des bins impossible — DaVinci Studio requis"

    def import_media_to_bin(self, file_path: str, sub_bin: str) -> bool:
        """Importe un fichier dans PANDORA > sub_bin, en créant le bin si nécessaire."""
        ok, result = _send("import_to_pandora_bin", {
            "path":    os.path.normpath(file_path),
            "sub_bin": sub_bin,
        })
        return ok and bool(result)

    def get_selected_clip_info(self) -> dict:
        _, info = _send("get_selected_clip")
        return info if isinstance(info, dict) else {}

    # ── Compatibilité avec l'ancien code ──────────────────────────────────────

    def get_media_pool(self):
        return None

    def get_current_timeline(self):
        return None


resolve = DaVinciConnection()
