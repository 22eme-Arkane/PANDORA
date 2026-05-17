"""
PANDORA Bridge Server — script à lancer depuis DaVinci Resolve.

Installation automatique : clique "Installer le bridge" dans PANDORA → Paramètres.
Ou copie manuellement ce fichier dans :
    C:\\ProgramData\\Blackmagic Design\\DaVinci Resolve\\Fusion\\Scripts\\Utility\\

Lancement :
    DaVinci Resolve → Espace de travail → Scripts → seedance_bridge

Une petite fenêtre s'ouvre pour confirmer que le bridge est actif.
Laisse-la ouverte pendant ta session.
"""

import builtins
import json
import os
import queue
import socket
import sys
import threading
import tkinter as tk

# ── Queues pour passer les appels DaVinci sur le thread principal ─────────────
_req_queue = queue.Queue()   # (cmd, params, result_queue)


_resolve   = None
_dvr_error = ""

# ── Tentative 1 : bmd injecté par DaVinci (contexte interne Scripts menu) ─────
try:
    _bmd = getattr(builtins, "bmd", None) or globals().get("bmd")
    if _bmd:
        _resolve = _bmd.scriptapp("Resolve")
        if _resolve is None:
            _dvr_error = "bmd OK mais scriptapp()→None"
    else:
        _dvr_error = "bmd non disponible (pas injecté par DaVinci)"
except Exception as _e:
    _dvr_error = f"bmd: {_e}"

# ── Tentative 2 : DaVinciResolveScript + env vars (scripting externe/hybride) ─
if _resolve is None:
    _INSTALL = r"C:\Program Files\Blackmagic Design\DaVinci Resolve"
    _MODS    = r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules"

    os.environ.setdefault(
        "RESOLVE_SCRIPT_API",
        r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting"
    )
    os.environ.setdefault(
        "RESOLVE_SCRIPT_LIB",
        os.path.join(_INSTALL, "fusionscript.dll")
    )
    if _INSTALL not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _INSTALL + os.pathsep + os.environ.get("PATH", "")

    for _p in [_MODS, _INSTALL]:
        if os.path.isdir(_p) and _p not in sys.path:
            sys.path.insert(0, _p)

    try:
        import importlib
        importlib.invalidate_caches()
        import DaVinciResolveScript as dvr
        _resolve = dvr.scriptapp("Resolve")
        if _resolve is None:
            _dvr_error = "Scripting API indisponible — DaVinci Studio requis"
        else:
            _dvr_error = ""
    except Exception as _e:
        _dvr_error = str(_e)[:140]


HOST = "127.0.0.1"
PORT = 19876


# ── Commandes DaVinci (doit s'exécuter sur le thread principal) ───────────────

def _handle(cmd: str, params: dict) -> object:
    """Toutes les commandes DaVinci doivent être appelées depuis le thread principal."""
    if cmd == "ping":
        return "pong"
    if cmd == "get_dvr_error":
        return _dvr_error
    if _resolve is None:
        raise RuntimeError(_dvr_error or "Resolve non disponible")

    pm      = _resolve.GetProjectManager()
    project = pm.GetCurrentProject() if pm else None

    if cmd == "get_project_name":
        return project.GetName() if project else ""

    if cmd == "get_timeline_name":
        if not project:
            return ""
        tl = project.GetCurrentTimeline()
        return tl.GetName() if tl else ""

    if cmd == "import_media":
        path = os.path.normpath(params.get("path", ""))
        if not project or not path:
            return False
        pool = project.GetMediaPool()
        return bool(pool.ImportMedia([path])) if pool else False

    if cmd == "create_pandora_bins":
        bins = params.get("bins", [])
        if not project:
            raise RuntimeError("Aucun projet DaVinci ouvert")
        pool = project.GetMediaPool()
        if not pool:
            raise RuntimeError("Media Pool inaccessible")
        root_folder = pool.GetRootFolder()
        existing = {f.GetName(): f for f in (root_folder.GetSubFolderList() or [])}
        pandora_bin = existing.get("PANDORA") or pool.AddSubFolder(root_folder, "PANDORA")
        if not pandora_bin:
            raise RuntimeError("Impossible de créer le bin PANDORA")
        existing_subs = {f.GetName() for f in (pandora_bin.GetSubFolderList() or [])}
        created = 0
        for name in bins:
            if name not in existing_subs:
                pool.AddSubFolder(pandora_bin, name)
                created += 1
        return {"total": len(bins), "created": created}

    if cmd == "import_to_pandora_bin":
        path    = os.path.normpath(params.get("path", ""))
        sub_bin = params.get("sub_bin", "")
        if not project or not os.path.isfile(path):
            return False
        pool = project.GetMediaPool()
        if not pool:
            return False
        root_folder = pool.GetRootFolder()
        ex_root = {f.GetName(): f for f in (root_folder.GetSubFolderList() or [])}
        pandora = ex_root.get("PANDORA") or pool.AddSubFolder(root_folder, "PANDORA")
        if not pandora:
            return False
        if sub_bin:
            ex_subs = {f.GetName(): f for f in (pandora.GetSubFolderList() or [])}
            target  = ex_subs.get(sub_bin) or pool.AddSubFolder(pandora, sub_bin)
        else:
            target = pandora
        if not target:
            return False
        pool.SetCurrentFolder(target)
        return bool(pool.ImportMedia([path]))

    if cmd == "get_selected_clip":
        if not project:
            return {}
        tl = project.GetCurrentTimeline()
        if not tl:
            return {}
        clip = tl.GetCurrentVideoItem()
        if not clip:
            return {}
        try:
            mi    = clip.GetMediaPoolItem()
            props = mi.GetClipProperty() if mi else {}
            return {
                "name":       props.get("Clip Name", ""),
                "file_path":  props.get("File Path", ""),
                "duration":   props.get("Duration", ""),
                "resolution": props.get("Resolution", ""),
                "fps":        props.get("FPS", ""),
            }
        except Exception:
            return {}

    if cmd == "get_timeline_clips":
        if not project:
            return []
        tl = project.GetCurrentTimeline()
        if not tl:
            return []
        clips = []
        try:
            n_tracks = int(tl.GetTrackCount("video"))
        except Exception:
            n_tracks = 1
        for track_idx in range(1, min(n_tracks + 1, 5)):
            try:
                items = tl.GetItemListInTrack("video", track_idx)
            except Exception:
                continue
            if not items:
                continue
            for item in (items if isinstance(items, list) else []):
                try:
                    mi    = item.GetMediaPoolItem()
                    props = mi.GetClipProperty() if mi else {}
                    fp    = props.get("File Path", "")
                    name  = props.get("Clip Name", "") or os.path.basename(fp)
                    if not name and not fp:
                        continue
                    clips.append({
                        "name":       name,
                        "file_path":  fp,
                        "duration":   props.get("Duration", ""),
                        "resolution": props.get("Resolution", ""),
                        "fps":        props.get("FPS", ""),
                        "track":      track_idx,
                    })
                except Exception:
                    pass
        return clips

    raise ValueError(f"Commande inconnue : {cmd}")


def _dispatch_on_main(root):
    """Polling 50 ms — exécute les commandes DaVinci en attente sur le thread principal."""
    try:
        while not _req_queue.empty():
            cmd, params, resp_q = _req_queue.get_nowait()
            try:
                result = _handle(cmd, params)
                resp_q.put(("ok", result))
            except Exception as exc:
                resp_q.put(("err", str(exc)))
    except Exception:
        pass
    root.after(50, lambda: _dispatch_on_main(root))


# ── Serveur TCP ───────────────────────────────────────────────────────────────

_clients = [0]

def _client(conn, addr, counter_var, root):
    _clients[0] += 1
    if counter_var and root:
        root.after(0, lambda: counter_var.set(f"Requêtes reçues : {_clients[0]}"))
    with conn:
        try:
            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
                if data.endswith(b"\n"):
                    break
            req  = json.loads(data.decode("utf-8"))
            cmd  = req.get("cmd", "")
            prms = req.get("params", {})

            if cmd == "ping":
                # ping sans appel DaVinci — réponse directe
                resp = json.dumps({"ok": True, "result": "pong"})
            else:
                # Commandes DaVinci → déléguer au thread principal via queue
                resp_q = queue.Queue()
                _req_queue.put((cmd, prms, resp_q))
                try:
                    status, result = resp_q.get(timeout=6.0)
                    if status == "ok":
                        resp = json.dumps({"ok": True, "result": result})
                    else:
                        resp = json.dumps({"ok": False, "error": result})
                except queue.Empty:
                    resp = json.dumps({"ok": False, "error": "Timeout — thread principal occupé"})
        except Exception as e:
            resp = json.dumps({"ok": False, "error": str(e)})
        conn.sendall((resp + "\n").encode("utf-8"))


def _start_server(counter_var=None, root=None):
    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, PORT))
        srv.listen(10)
        while True:
            conn, addr = srv.accept()
            threading.Thread(
                target=_client, args=(conn, addr, counter_var, root),
                daemon=True
            ).start()
    except Exception as e:
        if root and counter_var:
            root.after(0, lambda: counter_var.set(f"ERREUR serveur : {e}"))


# ── Fenêtre de statut tkinter ─────────────────────────────────────────────────

def _run_ui():
    has_error = not _resolve and _dvr_error
    height = 210 if has_error else 110
    root = tk.Tk()
    root.title("PANDORA Bridge")
    root.geometry(f"380x{height}")
    root.resizable(False, False)
    root.configure(bg="#111113")
    root.attributes("-topmost", True)

    tk.Label(
        root, text="◈  PANDORA BRIDGE",
        fg="#7c6bff", bg="#111113",
        font=("Consolas", 11, "bold")
    ).pack(pady=(12, 4))

    status_color = "#3ddc97" if _resolve else "#ff4f6a"
    status_text  = f"● Actif — TCP {HOST}:{PORT}" if _resolve else "✗  Resolve non accessible"
    tk.Label(
        root, text=status_text,
        fg=status_color, bg="#111113",
        font=("Consolas", 10, "bold")
    ).pack()

    if has_error:
        tk.Frame(root, bg="#2a2a30", height=1).pack(fill="x", padx=16, pady=(8, 6))
        tk.Label(
            root,
            text="Préférences → Avancé → colle :",
            fg="#888899", bg="#111113",
            font=("Consolas", 9)
        ).pack()
        tk.Label(
            root,
            text="ExternalScriptingEnabled = 1",
            fg="#ffcc55", bg="#1a1a22",
            font=("Consolas", 10, "bold"),
            padx=10, pady=4
        ).pack(pady=(2, 2))
        tk.Label(
            root,
            text="Puis Enregistrer → Redémarrer DaVinci",
            fg="#ff9966", bg="#111113",
            font=("Consolas", 9)
        ).pack()
        tk.Frame(root, bg="#2a2a30", height=1).pack(fill="x", padx=16, pady=(6, 4))

    counter_var = tk.StringVar(value="Requêtes reçues : 0")
    tk.Label(
        root, textvariable=counter_var,
        fg="#55556a", bg="#111113",
        font=("Consolas", 9)
    ).pack(pady=(2, 0))

    tk.Label(
        root, text="Laisse cette fenêtre ouverte pendant ta session.",
        fg="#3a3a4a", bg="#111113",
        font=("Consolas", 8)
    ).pack(pady=(2, 6))

    # Démarre le polling des commandes DaVinci sur le thread principal (50 ms)
    root.after(50, lambda: _dispatch_on_main(root))

    t = threading.Thread(target=_start_server, args=(counter_var, root), daemon=False)
    t.start()

    root.mainloop()


# ── Point d'entrée ────────────────────────────────────────────────────────────

_run_ui()
