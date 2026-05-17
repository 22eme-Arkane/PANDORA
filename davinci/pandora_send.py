"""
Envoie les clips de la timeline vers PANDORA — script DaVinci Resolve.

Installation automatique :
    Depuis PANDORA → Paramètres → bouton "Installer le script PANDORA dans DaVinci"
    Ou manuellement : copier ce fichier dans
    C:\\ProgramData\\Blackmagic Design\\DaVinci Resolve\\Fusion\\Scripts\\Utility\\

Raccourci clavier (recommandé : Ctrl+Shift+P) :
    DaVinci → Espace de travail → Personnalisation du clavier
    Catégorie "Scripts" → chercher "pandora_send" → assigner Ctrl+Shift+P

Utilisation :
    1. Dans DaVinci, la timeline active contient vos clips
    2. Espace de travail → Scripts → pandora_send  (ou votre raccourci)
    3. PANDORA détecte automatiquement les clips et les affiche dans
       AI Studio → onglet "Modifier depuis DaVinci Resolve"

Note technique :
    La fenêtre de confirmation est lancée dans un subprocess séparé pour
    éviter les conflits avec l'event loop Qt de DaVinci Resolve,
    notamment lors de l'exécution via raccourci clavier.
"""

import builtins
import json
import os
import subprocess
import sys
import tempfile

# ── Connexion DaVinci ─────────────────────────────────────────────────────────
_resolve = None
try:
    _bmd = getattr(builtins, "bmd", None) or globals().get("bmd")
    if _bmd:
        _resolve = _bmd.scriptapp("Resolve")
except Exception:
    pass

if _resolve is None:
    _INSTALL = r"C:\Program Files\Blackmagic Design\DaVinci Resolve"
    _MODS    = r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules"
    os.environ.setdefault(
        "RESOLVE_SCRIPT_API",
        r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting",
    )
    os.environ.setdefault(
        "RESOLVE_SCRIPT_LIB",
        os.path.join(_INSTALL, "fusionscript.dll"),
    )
    for _p in [_MODS, _INSTALL]:
        if os.path.isdir(_p) and _p not in sys.path:
            sys.path.insert(0, _p)
    try:
        import DaVinciResolveScript as dvr
        _resolve = dvr.scriptapp("Resolve")
    except Exception:
        pass

# ── Lecture des clips ─────────────────────────────────────────────────────────
clips         = []
timeline_name = ""
error         = ""
_has_any_flag = False

try:
    if not _resolve:
        error = "DaVinci Resolve non accessible — DaVinci Studio requis."
    else:
        pm      = _resolve.GetProjectManager()
        project = pm.GetCurrentProject() if pm else None
        tl      = project.GetCurrentTimeline() if project else None
        if not tl:
            error = "Aucune timeline ouverte dans DaVinci."
        else:
            timeline_name = tl.GetName()
            try:
                n_tracks = max(1, int(tl.GetTrackCount("video")))
            except Exception:
                n_tracks = 1

            # ── Détection des flags DaVinci sur les clips ─────────────────────
            # L'API DaVinci n'expose pas la sélection multi-clips de la timeline.
            # On utilise les flags natifs DaVinci comme mécanisme de sélection :
            #   Clic droit sur un clip → Flag → Red (ou toute autre couleur)
            #   → pandora_send n'envoie que les clips marqués.
            #   Si aucun clip n'a de flag → envoie toute la timeline (comportement par défaut).
            _flagged_by_track: dict = {}
            _has_any_flag = False
            for _ti in range(1, min(n_tracks + 1, 5)):
                try:
                    _all = tl.GetItemListInTrack("video", _ti) or []
                    _with_flag = []
                    for _it in (_all if isinstance(_all, list) else []):
                        try:
                            _fl = _it.GetFlagList()
                            if _fl:
                                _with_flag.append(_it)
                                _has_any_flag = True
                        except Exception:
                            pass
                    _flagged_by_track[_ti] = _with_flag
                except Exception:
                    pass

            # ── Lecture des clips (flaggés ou tous si aucun flag) ─────────────
            for track_idx in range(1, min(n_tracks + 1, 5)):
                if _has_any_flag:
                    track_items = _flagged_by_track.get(track_idx, [])
                else:
                    try:
                        track_items = tl.GetItemListInTrack("video", track_idx) or []
                    except Exception:
                        continue

                for item in (track_items if isinstance(track_items, list) else []):
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
except Exception as e:
    error = str(e)[:200]

# ── Écrire le fichier inbox (lu par PANDORA via QFileSystemWatcher) ───────────
INBOX = os.path.join(os.environ.get("TEMP", tempfile.gettempdir()), "pandora_clips_inbox.json")

if not error and clips:
    try:
        with open(INBOX, "w", encoding="utf-8") as f:
            json.dump({"timeline": timeline_name, "clips": clips}, f,
                      ensure_ascii=False, indent=2)
    except Exception as e:
        error = f"Impossible d'écrire le fichier inbox : {e}"

# ── Prépare le message de notification ───────────────────────────────────────
if error:
    msg, color = f"Erreur : {error}", "#ff4f6a"
elif not clips:
    if _has_any_flag:
        msg, color = "Aucun clip flaggé trouvé dans la timeline.", "#ffcc55"
    else:
        msg, color = "Aucun clip trouvé dans la timeline.", "#ffcc55"
else:
    if _has_any_flag:
        msg = f"{len(clips)} clip(s) sélectionné(s) envoyé(s) vers PANDORA"
        color = "#3ddc97"
    else:
        msg = f"{len(clips)} clip(s) envoyé(s) — toute la timeline\n(astuce : flagge tes clips pour n'envoyer que la sélection)"
        color = "#ffcc55"

# ── Notification dans un subprocess indépendant ───────────────────────────────
# Nécessaire car les scripts exécutés via raccourci clavier dans DaVinci
# tournent in-process (thread DaVinci/Qt) : tkinter.mainloop() y est incompatible.
# Le subprocess est totalement détaché — DaVinci n'attend pas sa fin.

_notif_script = os.path.join(tempfile.gettempdir(), "pandora_notif.py")
try:
    with open(_notif_script, "w", encoding="utf-8") as _f:
        _f.write(f"""\
import tkinter as tk
try:
    root = tk.Tk()
    root.title("PANDORA — Envoi clips")
    root.geometry("360x110")
    root.resizable(False, False)
    root.configure(bg="#111113")
    root.attributes("-topmost", True)
    tk.Label(
        root, text="◈  PANDORA — Envoyer vers AI Studio",
        fg="#7c6bff", bg="#111113", font=("Consolas", 10, "bold"),
    ).pack(pady=(12, 6))
    tk.Label(
        root, text={repr(msg)}, fg={repr(color)}, bg="#111113",
        font=("Consolas", 9), wraplength=320, justify="center",
    ).pack()
    tk.Button(
        root, text="OK", command=root.destroy,
        bg="#2a2a30", fg="#ccc", font=("Consolas", 9),
        bd=0, padx=20, pady=4, cursor="hand2",
    ).pack(pady=(8, 0))
    root.after(5000, root.destroy)
    root.mainloop()
except Exception:
    pass
""")
except Exception:
    _notif_script = None

if _notif_script:
    # Cherche un Python autonome capable d'afficher tkinter
    _python_candidates = []
    # 1. pythonw.exe (même répertoire que sys.executable, sans console Windows)
    _sysdir  = os.path.dirname(sys.executable)
    _pythonw = os.path.join(_sysdir, "pythonw.exe")
    if os.path.isfile(_pythonw):
        _python_candidates.append(_pythonw)
    # 2. sys.executable (Python de DaVinci)
    _python_candidates.append(sys.executable)
    # 3. Python standard dans %LOCALAPPDATA%
    for _ver in ("3.14", "3.13", "3.12", "3.11", "3.10"):
        for _subdir in (
            rf"C:\Users\{os.environ.get('USERNAME', '')}\AppData\Local\Python\pythoncore-{_ver}-64",
            rf"C:\Users\{os.environ.get('USERNAME', '')}\AppData\Local\Programs\Python\Python{_ver.replace('.', '')}",
        ):
            _candidate = os.path.join(_subdir, "pythonw.exe")
            if os.path.isfile(_candidate):
                _python_candidates.append(_candidate)
            _candidate = os.path.join(_subdir, "python.exe")
            if os.path.isfile(_candidate):
                _python_candidates.append(_candidate)

    _launched = False
    for _py in _python_candidates:
        try:
            subprocess.Popen(
                [_py, _notif_script],
                creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
                close_fds=True,
            )
            _launched = True
            break
        except Exception:
            continue

    # Fallback : MessageBox natif Windows (synchrone mais toujours disponible)
    if not _launched:
        try:
            import ctypes
            _icon = 0x10 if error else (0x30 if not clips else 0x40)
            ctypes.windll.user32.MessageBoxW(0, msg, "PANDORA — Envoi clips", _icon)
        except Exception:
            pass
