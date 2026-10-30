"""core/filmcraft.py — Le pont PANDORA → FilmCraft (le montage de la suite ArtCraft).

Demande Matthieu (27/10/2026) : « linker PANDORA avec la suite ArtCraft pour que ce
soit importé directement dans le logiciel de montage, automatiquement quand il est
lancé, comme on a fait pour DaVinci Resolve ».

FilmCraft (filmcraft.exe + filmcraft-cli.exe, 0.13.0 relevé le 27/10/2026) ouvre
un serveur de contrôle LOCAL (127.0.0.1, lignes JSON) quand on le lance avec
`--control <port>` (ou FILMCRAFT_CONTROL_PORT), à condition de lui donner un
jeton FILMCRAFT_CONTROL_TOKEN de 64 caractères hexadécimaux aléatoires.
`filmcraft-cli --bridge 127.0.0.1:<port>` y envoie les commandes de l'application
(menu Fichier, timeline…) avec le même jeton. PANDORA passe par la CLI : c'est
elle que FilmCraft tient à jour avec son protocole.

Vérifié en mode sans interface (projet temporaire) : `file.newBin` → {"bin": id},
`file.import` {"paths", "bin"} → {"items": [...], "errors": []},
`file.newSequence` → {"sequence": id}, `timeline.place` {"items", "track",
"seconds", "insert"} → clips bout à bout, `inspect project` → l'arbre des
chutiers. Le pont vers l'application ouverte, lui, n'a pas pu être essayé.

- Le jeton vit dans %LOCALAPPDATA%\\PANDORA\\filmcraft.token, jamais dans
  config.json ; seul le port est réglable (config `filmcraft_port`).
- Rangement comme pour DaVinci (core/timeline_clips) : chutier PANDORA, un
  sous-chutier par séquence (SQ03…), un fichier déjà présent n'est pas réimporté.
- Aucun Qt ici : les appels sont bloquants (quelques secondes au plus), à faire
  hors du fil de l'interface (core.background.run_task).
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys

DEFAULT_PORT = 47410
#: config : envoyer chaque clip généré à FilmCraft quand il est relié (vrai par défaut).
AUTO_KEY = "filmcraft_auto_import"
PORT_KEY = "filmcraft_port"
ROOT_BIN = "PANDORA"
_NO_WINDOW = 0x08000000 if sys.platform.startswith("win") else 0


# ── Installation ──────────────────────────────────────────────────────────────

def _candidates() -> list[str]:
    if sys.platform.startswith("win"):
        roots = [os.environ.get("ProgramFiles", r"C:\Program Files"),
                 os.environ.get("ProgramFiles(x86)", ""),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")]
        return [os.path.join(r, "FilmCraft") for r in roots if r]
    if sys.platform == "darwin":
        return ["/Applications/FilmCraft.app/Contents/MacOS",
                os.path.expanduser("~/Applications/FilmCraft.app/Contents/MacOS")]
    return ["/usr/bin", "/usr/local/bin", os.path.expanduser("~/.local/bin")]


def _exe(name: str) -> str:
    suffix = ".exe" if sys.platform.startswith("win") else ""
    for folder in _candidates():
        path = os.path.join(folder, name + suffix)
        if os.path.isfile(path):
            return path
    return ""


def app_path() -> str:
    return _exe("filmcraft")


def cli_path() -> str:
    return _exe("filmcraft-cli")


def is_installed() -> bool:
    return bool(app_path() and cli_path())


# ── Port et jeton ─────────────────────────────────────────────────────────────

def _cfg() -> dict:
    try:
        from core.config import load_config
        return load_config() or {}
    except Exception:
        return {}


def port() -> int:
    try:
        value = int(_cfg().get(PORT_KEY) or DEFAULT_PORT)
        return value if 1024 < value < 65536 else DEFAULT_PORT
    except (TypeError, ValueError):
        return DEFAULT_PORT


def auto_import_enabled(cfg: dict | None = None) -> bool:
    return bool((cfg if cfg is not None else _cfg()).get(AUTO_KEY, True))


def set_auto_import(enabled: bool) -> None:
    """save_config REMPLACE tout le fichier : on part de la config entière."""
    from core.config import load_config, save_config
    cfg = load_config()
    cfg[AUTO_KEY] = bool(enabled)
    save_config(cfg)


def token_path() -> str:
    if sys.platform == "darwin":
        root = os.path.expanduser("~/Library/Application Support/PANDORA")
    else:
        root = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "PANDORA")
    return os.path.join(root, "filmcraft.token")


def token() -> str:
    """Le jeton du pont (64 caractères hexadécimaux), créé au premier besoin."""
    path = token_path()
    try:
        with open(path, encoding="ascii") as f:
            value = f.read().strip()
        if len(value) == 64 and all(c in "0123456789abcdef" for c in value):
            return value
    except OSError:
        pass
    value = secrets.token_hex(32)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="ascii") as f:
        f.write(value)
    if not sys.platform.startswith("win"):
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return value


def control_env() -> dict:
    env = dict(os.environ)
    env["FILMCRAFT_CONTROL_PORT"] = str(port())
    env["FILMCRAFT_CONTROL_TOKEN"] = token()
    return env


# ── Lancer, joindre ───────────────────────────────────────────────────────────

def launch() -> tuple[bool, str]:
    """Ouvre FilmCraft relié à PANDORA (serveur de contrôle sur le port de PANDORA)."""
    app = app_path()
    if not app:
        return False, "not_installed"
    try:
        kwargs = {"env": control_env(), "close_fds": True}
        if sys.platform.startswith("win"):
            kwargs["creationflags"] = 0x00000008 | 0x00000200   # DETACHED | NEW_GROUP
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen([app, "--control", str(port())], **kwargs)
        return True, ""
    except OSError as exc:
        return False, str(exc)


def port_open(timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port()), timeout=timeout):
            return True
    except OSError:
        return False


def running() -> bool:
    """FilmCraft tourne-t-il (relié ou non) ? Sert à dire « ouvert sans le pont »."""
    try:
        if sys.platform.startswith("win"):
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq filmcraft.exe", "/NH"],
                                 capture_output=True, text=True, timeout=5,
                                 creationflags=_NO_WINDOW).stdout
            return "filmcraft.exe" in (out or "").lower()
        out = subprocess.run(["pgrep", "-x", "filmcraft"], capture_output=True, text=True,
                             timeout=5).stdout
        return bool((out or "").strip())
    except (OSError, subprocess.SubprocessError):
        return False


def cli(*args, timeout: float = 60.0) -> tuple[bool, object]:
    """Une commande au FilmCraft ouvert. (vrai, JSON rendu) ou (faux, message)."""
    exe = cli_path()
    if not exe:
        return False, "not_installed"
    try:
        r = subprocess.run([exe, "--compact", "--bridge", f"127.0.0.1:{port()}", *args],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, env=control_env(), creationflags=_NO_WINDOW)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except OSError as exc:
        return False, str(exc)
    out = (r.stdout or "").strip()
    if r.returncode != 0:
        return False, ((r.stderr or "").strip() or out or f"code {r.returncode}")[:500]
    try:
        return True, json.loads(out.splitlines()[-1]) if out else {}
    except ValueError:
        return True, out


def exec_cmd(command: str, params: dict | None = None, timeout: float = 60.0):
    return cli("exec", command, json.dumps(params or {}), timeout=timeout)


def status() -> str:
    """« not_installed », « closed » (pas lancé), « no_bridge » (lancé sans le pont
    de PANDORA) ou « ready »."""
    if not is_installed():
        return "not_installed"
    if port_open():
        ok, _ = cli("inspect", "project", timeout=15)
        if ok:
            return "ready"
    return "no_bridge" if running() else "closed"


# ── Chutiers, import, séquence ────────────────────────────────────────────────

def _find_child_bin(node: dict, name: str):
    for child in node.get("children") or []:
        if "type" not in child and child.get("name") == name and "id" in child:
            return child
    return None


def ensure_bin(path: list[str]) -> tuple[int | None, dict]:
    """L'identifiant du chutier PANDORA/… (créé au besoin) et son nœud."""
    ok, tree = cli("inspect", "project", timeout=20)
    if not ok or not isinstance(tree, dict):
        raise RuntimeError(str(tree))
    node = tree.get("root") or {}
    parent = None
    for name in [n for n in path if n]:
        child = _find_child_bin(node, name)
        if child is None:
            params = {"name": name}
            if parent is not None:
                params["parent"] = parent
            ok, res = exec_cmd("file.newBin", params)
            if not ok or not isinstance(res, dict) or "bin" not in res:
                raise RuntimeError(str(res))
            child = {"id": res["bin"], "name": name, "children": []}
        parent, node = child["id"], child
    return parent, node


def _existing(node: dict, filename: str):
    for child in node.get("children") or []:
        if child.get("type") and child.get("name") == filename and "item" in child:
            return child["item"]
    return None


def import_files(paths: list[str], sub_bin: str = "") -> dict:
    """Importe dans PANDORA/<sub_bin>. → {"map": {chemin: id}, "items": [ids dans
    l'ordre], "reused": n, "errors": [...]} ; lève RuntimeError si FilmCraft ne
    répond pas. Un fichier absent n'a simplement pas d'identifiant."""
    bin_id, node = ensure_bin([ROOT_BIN, sub_bin])
    items, todo, reused = {}, [], 0
    for path in paths:
        found = _existing(node, os.path.basename(path))
        if found is not None:
            items[path] = found
            reused += 1
        elif os.path.isfile(path):
            todo.append(path)
    errors = []
    if todo:
        ok, res = exec_cmd("file.import", {"paths": [os.path.abspath(p) for p in todo],
                                           "bin": bin_id}, timeout=180)
        if not ok or not isinstance(res, dict):
            raise RuntimeError(str(res))
        for path, item in zip(todo, res.get("items") or []):
            items[path] = item
        errors = [str(e) for e in res.get("errors") or []]
    return {"map": items, "items": [items[p] for p in paths if p in items],
            "reused": reused, "errors": errors}


def import_clip(path: str, sub_bin: str = "") -> tuple[bool, str]:
    """L'import automatique d'un clip généré (comme davinci.importer)."""
    try:
        res = import_files([path], sub_bin)
    except RuntimeError as exc:
        return False, str(exc)
    if res["errors"]:
        return False, "; ".join(res["errors"])[:300]
    return bool(res["items"]), ""


def build_sequence(name: str, clips: list[dict], width: int = 1920, height: int = 1080,
                   fps: float = 24.0) -> tuple[bool, object]:
    """Monte les clips ({"path", "bin"} dans l'ordre) bout à bout sur une nouvelle
    séquence. (vrai, {"sequence", "count", "reused", "errors"}) ou (faux, message)."""
    try:
        reused, errors = 0, []
        by_bin: dict = {}
        for clip in clips:
            by_bin.setdefault(clip.get("bin") or "", []).append(clip["path"])
        placed: dict = {}
        for sub_bin, paths in by_bin.items():
            res = import_files(paths, sub_bin)
            reused += res["reused"]
            errors += res["errors"]
            placed.update(res["map"])
        ids = [placed[c["path"]] for c in clips if c["path"] in placed]
        if not ids:
            return False, "; ".join(errors) or "no_clip"
        ok, seq = exec_cmd("file.newSequence", {"name": name, "width": int(width),
                                                "height": int(height), "fps": float(fps)})
        if not ok or not isinstance(seq, dict) or "sequence" not in seq:
            return False, str(seq)
        ok, res = exec_cmd("timeline.place", {"items": ids, "track": "V1", "seconds": 0,
                                              "insert": False}, timeout=180)
        if not ok:
            return False, str(res)
        return True, {"sequence": seq["sequence"], "count": len(ids), "reused": reused,
                      "errors": errors}
    except RuntimeError as exc:
        return False, str(exc)


# ── « Toujours relier » : FilmCraft ouvert depuis le menu Démarrer ────────────

def _env_keys() -> tuple[str, str]:
    return "FILMCRAFT_CONTROL_PORT", "FILMCRAFT_CONTROL_TOKEN"


def always_linked() -> bool:
    """Les variables d'environnement de l'utilisateur relient-elles déjà FilmCraft ?"""
    if not sys.platform.startswith("win"):
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, "FILMCRAFT_CONTROL_TOKEN")
        with open(token_path(), encoding="ascii") as f:     # lecture seule : pas de création
            return value == f.read().strip()
    except OSError:
        return False


def set_always_linked(enabled: bool) -> tuple[bool, str]:
    """Windows seulement, sur demande de l'utilisateur (case des Paramètres) :
    enregistre le port et le jeton dans les variables d'environnement de SON
    compte, pour que FilmCraft ouvre le pont même lancé hors de PANDORA. Prend
    effet au prochain lancement de FilmCraft."""
    if not sys.platform.startswith("win"):
        return False, "windows_only"
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                            winreg.KEY_SET_VALUE) as key:
            port_key, token_key = _env_keys()
            if enabled:
                winreg.SetValueEx(key, port_key, 0, winreg.REG_SZ, str(port()))
                winreg.SetValueEx(key, token_key, 0, winreg.REG_SZ, token())
            else:
                for name in (port_key, token_key):
                    try:
                        winreg.DeleteValue(key, name)
                    except OSError:
                        pass
        _broadcast_env_change()
        return True, ""
    except OSError as exc:
        return False, str(exc)


def _broadcast_env_change() -> None:
    """Prévient l'Explorateur que l'environnement a changé (sinon il faut se
    reconnecter pour qu'un raccourci du menu Démarrer en hérite)."""
    try:
        import ctypes
        HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG = 0xFFFF, 0x001A, 0x0002
        ctypes.windll.user32.SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0,
                                                 "Environment", SMTO_ABORTIFHUNG, 2000, None)
    except Exception:
        pass
