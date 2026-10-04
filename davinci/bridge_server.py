"""
PANDORA Bridge — script lancé DANS DaVinci Resolve :

    DaVinci Resolve → Espace de travail → Scripts → seedance_bridge

Installation : PANDORA → Paramètres → DaVinci Resolve → « Installer / mettre à
jour les scripts DaVinci » (l'installeur de PANDORA le copie aussi quand Resolve
est déjà présent). Resolve ne liste un NOUVEAU script qu'à son démarrage.

Prérequis Blackmagic (README Scripting) : jusqu'à Resolve 20.x, un Python 3
64 bits installé sur le poste (« for all users ») ; Resolve 21.1 et suivants
embarquent leur propre Python mais réservent le scripting à la version Studio.

Une petite fenêtre confirme que le pont est actif. La fermer ARRÊTE le pont :
la version 1 laissait un serveur « zombie » qui répondait au ping sans plus rien
exécuter (voyant vert dans PANDORA, chaque import échouait au bout de 3 s).
Sans tkinter (Python embarqué de Resolve 21.1), le pont tourne sans fenêtre et
s'arrête avec Resolve.

Syntaxe volontairement compatible Python 3.6 : c'est le Python du poste (ou
celui de Resolve) qui exécute ce fichier, pas celui de PANDORA.
"""

BRIDGE_VERSION = 2

import builtins
import json
import os
import queue
import socket
import sys
import threading
import time

try:
    import tkinter as tk
except Exception:          # Python sans Tk (Resolve 21.1 embarque le sien)
    tk = None

HOST = "127.0.0.1"
PORT = int(os.environ.get("PANDORA_BRIDGE_PORT") or 19876)

# Attente maximale d'une commande par la boucle principale (secondes). Le client
# PANDORA attend toujours PLUS longtemps (sinon un import réussi après coup était
# déclaré raté — délais 3 s client / 6 s serveur de la version 1).
WAIT_DEFAULT = 8.0
WAIT_LONG = 180.0
_LONG_COMMANDS = ("import_clips", "build_timeline")
_QUIET_COMMANDS = ("ping", "status", "get_project_name", "get_timeline_name",
                   "get_dvr_error")
# Champs de métadonnées standard de Resolve ; les autres clés partent en
# métadonnées « tierces » (SetThirdPartyMetadata).
_STD_META = ("Scene", "Shot", "Take", "Comments", "Description", "Keywords")


# ── Langue de la fenêtre (celle du poste) ─────────────────────────────────────

def _is_french():
    try:
        if sys.platform.startswith("win"):
            import ctypes
            return (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x0C
    except Exception:
        pass
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        value = os.environ.get(var) or ""
        if value:
            return value.lower().startswith("fr")
    return True


_FR = _is_french()


def _t(fr, en):
    return fr if _FR else en


# ── Accès à l'API Resolve ─────────────────────────────────────────────────────

_resolve = None
_dvr_error = ""
_PRODUCT = ""
_VERSION = ""


def _injected(name):
    value = globals().get(name)
    if value is None:
        value = getattr(builtins, name, None)
    return value


def _prepare_external_env():
    """Variables du scripting « externe » (README Scripting, section Using a script)."""
    if sys.platform.startswith("win"):
        pdata = os.environ.get("PROGRAMDATA") or r"C:\ProgramData"
        pfiles = os.environ.get("PROGRAMFILES") or r"C:\Program Files"
        api = os.path.join(pdata, "Blackmagic Design", "DaVinci Resolve", "Support",
                           "Developer", "Scripting")
        install = os.path.join(pfiles, "Blackmagic Design", "DaVinci Resolve")
        lib = os.path.join(install, "fusionscript.dll")
    elif sys.platform == "darwin":
        api = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
        install = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion"
        lib = os.path.join(install, "fusionscript.so")
    else:
        api = "/opt/resolve/Developer/Scripting"
        install = "/opt/resolve/libs/Fusion"
        lib = os.path.join(install, "fusionscript.so")
    os.environ.setdefault("RESOLVE_SCRIPT_API", api)
    os.environ.setdefault("RESOLVE_SCRIPT_LIB", lib)
    for path in (os.path.join(os.environ["RESOLVE_SCRIPT_API"], "Modules"), install):
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)
    if sys.platform.startswith("win") and os.path.isdir(install) \
            and install not in os.environ.get("PATH", ""):
        os.environ["PATH"] = install + os.pathsep + os.environ.get("PATH", "")


def _acquire_resolve():
    """(objet Resolve, "") ou (None, raison)."""
    reasons = []
    obj = _injected("resolve")
    if obj is not None:
        return obj, ""
    bmd = _injected("bmd")
    if bmd is not None:
        try:
            obj = bmd.scriptapp("Resolve")
            if obj is not None:
                return obj, ""
            reasons.append("bmd.scriptapp('Resolve') → None")
        except Exception as exc:
            reasons.append("bmd : " + str(exc)[:120])
    # Repli : scripting externe (Studio + Préférences → Système → Général →
    # « External scripting using : Local »).
    try:
        _prepare_external_env()
        import importlib
        importlib.invalidate_caches()
        import DaVinciResolveScript as dvr
        obj = dvr.scriptapp("Resolve")
        if obj is not None:
            return obj, ""
        reasons.append("DaVinciResolveScript.scriptapp('Resolve') → None")
    except Exception as exc:
        reasons.append(str(exc)[:160])
    return None, "API DaVinci Resolve inaccessible (" + " ; ".join(reasons) + ")"


def _product():
    name = version = ""
    if _resolve is None:
        return name, version
    try:
        name = str(_resolve.GetProductName() or "")
    except Exception:
        pass
    try:
        version = str(_resolve.GetVersionString() or "")
    except Exception:
        pass
    return name, version


# ── Media Pool ────────────────────────────────────────────────────────────────

def _project():
    manager = _resolve.GetProjectManager()
    return manager.GetCurrentProject() if manager else None


def _need_project():
    project = _project()
    if not project:
        raise RuntimeError("Aucun projet ouvert dans DaVinci Resolve")
    return project


def _media_pool(project):
    pool = project.GetMediaPool()
    if not pool:
        raise RuntimeError("Media Pool inaccessible")
    return pool


def _child_folder(folder, name):
    for sub in (folder.GetSubFolderList() or []):
        try:
            if sub.GetName() == name:
                return sub
        except Exception:
            continue
    return None


def _pandora_folder(pool, sub_bin=""):
    root = pool.GetRootFolder()
    pandora = _child_folder(root, "PANDORA") or pool.AddSubFolder(root, "PANDORA")
    if not pandora:
        raise RuntimeError("Impossible de créer le chutier PANDORA")
    if not sub_bin:
        return pandora
    target = _child_folder(pandora, sub_bin) or pool.AddSubFolder(pandora, sub_bin)
    if not target:
        raise RuntimeError("Impossible de créer le chutier PANDORA/" + sub_bin)
    return target


def _same_file(a, b):
    return os.path.normcase(os.path.normpath(a or "")) == \
        os.path.normcase(os.path.normpath(b or ""))


def _find_clip(folder, path):
    for clip in (folder.GetClipList() or []):
        try:
            if _same_file(clip.GetClipProperty("File Path"), path):
                return clip
        except Exception:
            continue
    return None


def _apply_meta(item, meta, color):
    for key, value in (meta or {}).items():
        if value in (None, ""):
            continue
        try:
            if key in _STD_META:
                item.SetMetadata(key, str(value))
            else:
                item.SetThirdPartyMetadata(str(key), str(value))
        except Exception:
            pass
    if color:
        try:
            item.SetClipColor(color)
        except Exception:
            pass


def _import_clip(pool, path, sub_bin="", meta=None, color=""):
    """Importe `path` dans PANDORA[/sub_bin] — ou réutilise le clip déjà présent.
    Rétablit le chutier que l'utilisateur regardait. → (MediaPoolItem, déjà_là)."""
    path = os.path.normpath(path or "")
    if not path or not os.path.isfile(path):
        raise RuntimeError("Fichier introuvable : " + (path or "?"))
    folder = _pandora_folder(pool, sub_bin)
    item = _find_clip(folder, path)
    reused = item is not None
    if item is None:
        previous = None
        try:
            previous = pool.GetCurrentFolder()
        except Exception:
            pass
        try:
            pool.SetCurrentFolder(folder)
            items = pool.ImportMedia([path]) or []
        finally:
            if previous is not None:
                try:
                    pool.SetCurrentFolder(previous)
                except Exception:
                    pass
        item = items[0] if items else None
        if item is None:
            raise RuntimeError("Import refusé par DaVinci Resolve : " + os.path.basename(path))
    _apply_meta(item, meta, color)
    return item, reused


def _timeline_names(project):
    names = set()
    try:
        count = int(project.GetTimelineCount() or 0)
    except Exception:
        count = 0
    for index in range(1, count + 1):
        try:
            timeline = project.GetTimelineByIndex(index)
            if timeline:
                names.add(timeline.GetName())
        except Exception:
            continue
    return names


def _unique_timeline_name(project, base):
    names = _timeline_names(project)
    if base not in names:
        return base
    n = 2
    while "%s (%d)" % (base, n) in names:
        n += 1
    return "%s (%d)" % (base, n)


def _build_timeline(params):
    """Monte les clips DANS L'ORDRE reçu sur une nouvelle timeline (le nom est
    rendu unique) rangée dans le chutier PANDORA, puis l'ouvre."""
    project = _need_project()
    pool = _media_pool(project)
    base = str(params.get("name") or "PANDORA").strip() or "PANDORA"
    items, missing, errors, reused = [], [], [], 0
    for clip in params.get("clips") or []:
        path = str(clip.get("path") or "")
        if not os.path.isfile(path):
            missing.append(path)
            continue
        try:
            item, already = _import_clip(pool, path, clip.get("bin") or "",
                                         clip.get("meta"), clip.get("color") or "")
        except Exception as exc:
            errors.append(str(exc))
            continue
        reused += 1 if already else 0
        items.append(item)
    if not items:
        raise RuntimeError("Aucun clip n'a pu être importé dans DaVinci Resolve"
                           + (" : " + errors[0] if errors else ""))
    name = _unique_timeline_name(project, base)
    previous = None
    try:
        previous = pool.GetCurrentFolder()
    except Exception:
        pass
    try:
        pool.SetCurrentFolder(_pandora_folder(pool, ""))
        timeline = pool.CreateTimelineFromClips(name, items)
    finally:
        if previous is not None:
            try:
                pool.SetCurrentFolder(previous)
            except Exception:
                pass
    if not timeline:
        raise RuntimeError("DaVinci Resolve a refusé de créer la timeline « %s »" % name)
    try:
        project.SetCurrentTimeline(timeline)
    except Exception:
        pass
    return {"timeline": name, "count": len(items), "reused": reused,
            "missing": missing, "errors": errors}


def _clip_props(item):
    media = item.GetMediaPoolItem()
    props = media.GetClipProperty() if media else {}
    path = props.get("File Path", "")
    return {
        "name": props.get("Clip Name", "") or os.path.basename(path),
        "file_path": path,
        "duration": props.get("Duration", ""),
        "resolution": props.get("Resolution", ""),
        "fps": props.get("FPS", ""),
    }


# ── Commandes (exécutées par la boucle principale) ────────────────────────────

def _ping_payload():
    return {"pong": True, "bridge": BRIDGE_VERSION, "api_ok": _resolve is not None,
            "product": _PRODUCT, "version": _VERSION, "error": _dvr_error,
            "python": sys.version.split()[0], "window": bool(_window_alive[0])}


def _handle(cmd, params):
    if cmd == "ping":
        return _ping_payload()
    if cmd == "get_dvr_error":
        return _dvr_error
    if cmd == "shutdown":
        _request_stop()
        return True
    if _resolve is None:
        raise RuntimeError(_dvr_error or "API DaVinci Resolve inaccessible")

    if cmd == "status":
        project = _project()
        timeline = project.GetCurrentTimeline() if project else None
        return {"project": project.GetName() if project else "",
                "timeline": timeline.GetName() if timeline else ""}
    if cmd == "get_project_name":
        project = _project()
        return project.GetName() if project else ""
    if cmd == "get_timeline_name":
        project = _project()
        timeline = project.GetCurrentTimeline() if project else None
        return timeline.GetName() if timeline else ""

    if cmd == "import_media":                       # compatibilité version 1
        pool = _media_pool(_need_project())
        path = os.path.normpath(params.get("path") or "")
        if not os.path.isfile(path):
            raise RuntimeError("Fichier introuvable : " + path)
        return bool(pool.ImportMedia([path]))
    if cmd == "create_pandora_bins":
        pool = _media_pool(_need_project())
        pandora = _pandora_folder(pool, "")
        existing = set()
        for sub in (pandora.GetSubFolderList() or []):
            try:
                existing.add(sub.GetName())
            except Exception:
                continue
        created = 0
        for name in params.get("bins") or []:
            if name not in existing:
                pool.AddSubFolder(pandora, name)
                created += 1
        return {"total": len(params.get("bins") or []), "created": created}
    if cmd == "import_to_pandora_bin":
        pool = _media_pool(_need_project())
        item, reused = _import_clip(pool, params.get("path"), params.get("sub_bin") or "",
                                    params.get("meta"), params.get("color") or "")
        try:
            name = item.GetName()
        except Exception:
            name = os.path.basename(str(params.get("path") or ""))
        return {"name": name, "reused": reused, "bin": params.get("sub_bin") or ""}
    if cmd == "import_clips":
        pool = _media_pool(_need_project())
        results = []
        for clip in params.get("clips") or []:
            try:
                _item, reused = _import_clip(pool, clip.get("path"), clip.get("bin") or "",
                                             clip.get("meta"), clip.get("color") or "")
                results.append({"path": clip.get("path"), "ok": True, "reused": reused})
            except Exception as exc:
                results.append({"path": clip.get("path"), "ok": False, "error": str(exc)})
        return results
    if cmd == "build_timeline":
        return _build_timeline(params)

    if cmd == "get_selected_clip":
        project = _project()
        timeline = project.GetCurrentTimeline() if project else None
        item = timeline.GetCurrentVideoItem() if timeline else None
        if not item:
            return {}
        try:
            return _clip_props(item)
        except Exception:
            return {}
    if cmd == "get_timeline_clips":
        project = _project()
        timeline = project.GetCurrentTimeline() if project else None
        if not timeline:
            return []
        try:
            tracks = int(timeline.GetTrackCount("video") or 1)
        except Exception:
            tracks = 1
        clips = []
        for track in range(1, tracks + 1):           # TOUTES les pistes (v1 : V1 à V4)
            try:
                items = timeline.GetItemListInTrack("video", track) or []
            except Exception:
                continue
            for item in (items if isinstance(items, list) else []):
                try:
                    info = _clip_props(item)
                except Exception:
                    continue
                if info["name"] or info["file_path"]:
                    info["track"] = track
                    clips.append(info)
        return clips

    raise ValueError("Commande inconnue : " + str(cmd))


# ── Boucle principale + serveur TCP ───────────────────────────────────────────

_requests = queue.Queue()
_stop = threading.Event()
_server = [None]
_window_alive = [False]
_last_tick = [0.0]
_busy = [False]
_request_count = [0]


def _dispatch_pending():
    while True:
        try:
            cmd, params, answer = _requests.get_nowait()
        except queue.Empty:
            return
        _busy[0] = True
        try:
            answer.put(("ok", _handle(cmd, params)))
        except Exception as exc:
            answer.put(("err", str(exc) or exc.__class__.__name__))
        finally:
            _busy[0] = False


def _tick():
    _last_tick[0] = time.monotonic()
    _dispatch_pending()


def _loop_alive():
    return _busy[0] or (time.monotonic() - _last_tick[0]) < 3.0


def _serve_client(conn):
    with conn:
        response = None
        try:
            conn.settimeout(10.0)
            data = b""
            while not data.endswith(b"\n"):
                chunk = conn.recv(65536)
                if not chunk:
                    break
                data += chunk
            request = json.loads(data.decode("utf-8"))
            cmd = str(request.get("cmd") or "")
            params = request.get("params") or {}
            if _stop.is_set():
                raise RuntimeError("Pont PANDORA en cours d'arrêt")
            if cmd == "ping":
                # Réponse directe, mais seulement si la boucle principale vit
                # encore : c'est elle qui exécute les commandes.
                if not _loop_alive():
                    raise RuntimeError("Boucle du pont arrêtée — relancez seedance_bridge")
                response = {"ok": True, "result": _ping_payload()}
            elif cmd == "shutdown":
                # Traité ICI, pas par la boucle : une relance du script doit pouvoir
                # remplacer un pont dont la boucle est figée.
                _request_stop()
                response = {"ok": True, "result": True}
            else:
                answer = queue.Queue()
                _requests.put((cmd, params, answer))
                wait = WAIT_LONG if cmd in _LONG_COMMANDS else WAIT_DEFAULT
                try:
                    status, result = answer.get(timeout=wait)
                except queue.Empty:
                    status, result = "err", ("Délai dépassé — DaVinci Resolve est occupé "
                                             "(rendu, fenêtre ouverte…)")
                if cmd not in _QUIET_COMMANDS:
                    _request_count[0] += 1
                response = ({"ok": True, "result": result} if status == "ok"
                            else {"ok": False, "error": result})
        except Exception as exc:
            response = {"ok": False, "error": str(exc) or exc.__class__.__name__}
        try:
            conn.sendall((json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))
            # Le CLIENT ferme en premier : l'attente TIME_WAIT reste de son côté et
            # le port reste disponible pour une relance immédiate du pont.
            conn.settimeout(2.0)
            conn.recv(1)
        except Exception:
            pass


def _open_server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    exclusive = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
    if exclusive is not None:
        # Windows : un 2e pont ne peut plus s'asseoir sur le même port
        # (SO_REUSEADDR de la version 1 → comportement indéterminé).
        srv.setsockopt(socket.SOL_SOCKET, exclusive, 1)
    else:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(16)
    return srv


def _stop_previous_bridge():
    """Demande à un pont déjà lancé (version 2+) de s'arrêter : relancer le
    script remplace l'ancien pont au lieu de s'empiler dessus."""
    try:
        conn = socket.create_connection((HOST, PORT), timeout=1.0)
    except OSError:
        return False
    try:
        conn.settimeout(3.0)
        conn.sendall(b'{"cmd": "shutdown", "params": {}}\n')
        reply = conn.recv(4096)
        return b'"ok": true' in reply
    except Exception:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _bind_with_takeover():
    try:
        return _open_server(), ""
    except OSError:
        pass
    if _stop_previous_bridge():
        for _attempt in range(20):
            time.sleep(0.25)
            try:
                return _open_server(), ""
            except OSError:
                continue
    return None, _t(
        "Port %d déjà utilisé : un ancien pont PANDORA tourne encore.\n"
        "Fermez sa fenêtre, ou redémarrez DaVinci Resolve." % PORT,
        "Port %d already in use: an older PANDORA bridge is still running.\n"
        "Close its window, or restart DaVinci Resolve." % PORT)


def _accept_loop(srv):
    while not _stop.is_set():
        try:
            conn, _addr = srv.accept()
        except OSError:
            break                                   # socket fermée par _request_stop
        threading.Thread(target=_serve_client, args=(conn,), daemon=True).start()


def _request_stop():
    _stop.set()
    srv = _server[0]
    _server[0] = None
    if srv is not None:
        try:
            srv.close()
        except Exception:
            pass


# ── Fenêtre de statut (tkinter) ou mode sans fenêtre ──────────────────────────

_BG = "#0c0e1a"


def _run_window(bind_error):
    root = tk.Tk()
    _window_alive[0] = True
    pending = {}                     # rappels « after » à annuler avant destroy()
    root.title("PANDORA Bridge")
    root.resizable(False, False)
    root.configure(bg=_BG)
    # Au premier plan le temps d'être vue, puis elle laisse Resolve devant.
    root.attributes("-topmost", True)
    pending["top"] = root.after(2500, lambda: root.attributes("-topmost", False))

    def label(text, color, size=9, bold=False, pady=(0, 0), bg=_BG):
        tk.Label(root, text=text, fg=color, bg=bg, justify="center",
                 font=("Consolas", size, "bold" if bold else "normal"),
                 wraplength=380).pack(padx=14, pady=pady)

    label("◈  PANDORA BRIDGE  ·  v%d" % BRIDGE_VERSION, "#7c6bff", 11, True, (12, 4))
    if bind_error:
        label("✗  " + _t("Pont non démarré", "Bridge not started"), "#ff4f6a", 10, True)
        label(bind_error, "#ffcc55", 9, False, (6, 4))
    elif _resolve is None:
        label("✗  " + _t("API DaVinci Resolve inaccessible",
                         "DaVinci Resolve API unavailable"), "#ff4f6a", 10, True)
        label(_t("Lancez ce script depuis Espace de travail → Scripts,\n"
                 "avec un projet ouvert.\n"
                 "Resolve 21.1 et suivants : scripting réservé à Studio.",
                 "Run this script from Workspace → Scripts,\n"
                 "with a project open.\n"
                 "Resolve 21.1 and later: scripting requires Studio."),
              "#ffcc55", 9, False, (6, 2))
        label(_dvr_error[:220], "#55556a", 8, False, (2, 4))
    else:
        label("●  " + _t("Actif", "Active") + " — %s:%d" % (HOST, PORT), "#3ddc97", 10, True)
        if _PRODUCT or _VERSION:
            label(("%s %s" % (_PRODUCT, _VERSION)).strip(), "#888899", 9, False, (2, 0))

    counter = tk.StringVar(value="")
    tk.Label(root, textvariable=counter, fg="#55556a", bg=_BG,
             font=("Consolas", 9)).pack(pady=(6, 0))
    label(_t("Laissez cette fenêtre ouverte : la fermer arrête le pont.",
             "Keep this window open: closing it stops the bridge."),
          "#6a6a82", 8, False, (2, 10))

    def close():
        _request_stop()
        _window_alive[0] = False
        for after_id in pending.values():
            try:
                root.after_cancel(after_id)
            except Exception:
                pass
        try:
            root.destroy()
        except Exception:
            pass

    def poll():
        if _stop.is_set():
            close()
            return
        _tick()
        counter.set(_t("Requêtes traitées : %d", "Requests handled: %d") % _request_count[0])
        pending["poll"] = root.after(50, poll)

    root.protocol("WM_DELETE_WINDOW", close)
    pending["poll"] = root.after(50, poll)
    root.mainloop()
    _window_alive[0] = False


def _run_headless():
    print("PANDORA Bridge v%d — %s:%d (%s)" % (
        BRIDGE_VERSION, HOST, PORT, _t("sans fenêtre", "no window")))
    next_check = time.monotonic() + 10.0
    while not _stop.is_set():
        _tick()
        if time.monotonic() >= next_check:
            next_check = time.monotonic() + 10.0
            try:
                gone = _resolve.GetProductName() is None
            except Exception:
                gone = True
            if gone:                                 # Resolve fermé : le pont s'arrête
                break
        time.sleep(0.05)
    _request_stop()


def main():
    global _resolve, _dvr_error, _PRODUCT, _VERSION
    _resolve, _dvr_error = _acquire_resolve()
    _PRODUCT, _VERSION = _product()
    srv, bind_error = _bind_with_takeover()
    if srv is not None:
        _server[0] = srv
        threading.Thread(target=_accept_loop, args=(srv,), daemon=True).start()
    if tk is not None:
        try:
            _run_window(bind_error)
        except Exception as exc:                     # Tk présent mais inutilisable
            print("PANDORA Bridge : " + _t("fenêtre impossible", "no window") + " (%s)" % exc)
            if _window_alive[0] or _stop.is_set():   # la fenêtre a vécu : on s'arrête
                _window_alive[0] = False
                _request_stop()
                return
        else:
            _request_stop()                          # fenêtre fermée = pont arrêté
            return
    if srv is None or _resolve is None:
        print("PANDORA Bridge : " + (bind_error or _dvr_error))
        _request_stop()
        return
    _run_headless()


if not os.environ.get("PANDORA_BRIDGE_NO_AUTORUN"):
    main()
