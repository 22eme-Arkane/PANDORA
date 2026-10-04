"""
Installation et mise à jour des scripts PANDORA dans DaVinci Resolve.

    seedance_bridge.py  (= davinci/bridge_server.py)  → Espace de travail → Scripts
    pandora_send.py                                    → Espace de travail → Scripts

Resolve liste les scripts des dossiers « Utility » (README Scripting) :
  • tous les utilisateurs : %PROGRAMDATA%\\Blackmagic Design\\DaVinci Resolve\\Fusion\\Scripts\\Utility
  • l'utilisateur seul     : %APPDATA%\\Blackmagic Design\\DaVinci Resolve\\Support\\Fusion\\Scripts\\Utility
    (le README écrit « %APPDATA%\\Roaming\\… » : coquille, %APPDATA% EST Roaming)

Pourquoi un bouton dans PANDORA (audit DaVinci du 04/10/2026) : l'installeur ne
copiait les scripts que si Resolve était DÉJÀ installé, au chemin par défaut, et
rien ne permettait ensuite de réparer ni de savoir qu'un pont était périmé
(constat sur le poste de Matthieu : seedance_bridge.py du 15/05 ≠ dépôt du 17/05).
Chaque script porte désormais un numéro de version lisible sans le lancer.
"""

import os
import re
import shutil
import sys

BRIDGE_FILE = "seedance_bridge.py"
SEND_FILE = "pandora_send.py"
# (fichier livré dans PANDORA, nom une fois installé dans Resolve, constante de version)
SCRIPTS = (
    ("bridge_server.py", BRIDGE_FILE, "BRIDGE_VERSION"),
    ("pandora_send.py", SEND_FILE, "SCRIPT_VERSION"),
)


def _source_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(getattr(sys, "_MEIPASS", ""), "davinci")
    return os.path.dirname(os.path.abspath(__file__))


def resolve_roots() -> list[tuple[str, str]]:
    """[(portée, dossier « DaVinci Resolve » de cette portée)]."""
    if sys.platform.startswith("win"):
        pdata = os.environ.get("PROGRAMDATA") or r"C:\ProgramData"
        appdata = os.environ.get("APPDATA") or os.path.join(
            os.path.expanduser("~"), "AppData", "Roaming")
        return [("all", os.path.join(pdata, "Blackmagic Design", "DaVinci Resolve")),
                ("user", os.path.join(appdata, "Blackmagic Design", "DaVinci Resolve"))]
    if sys.platform == "darwin":
        return [("all", "/Library/Application Support/Blackmagic Design/DaVinci Resolve"),
                ("user", os.path.expanduser(
                    "~/Library/Application Support/Blackmagic Design/DaVinci Resolve"))]
    return [("all", "/opt/resolve"),
            ("user", os.path.expanduser("~/.local/share/DaVinciResolve"))]


def utility_dirs() -> list[tuple[str, str]]:
    """[(portée, dossier Utility)] — tous les utilisateurs d'abord, puis l'utilisateur."""
    out = []
    for scope, root in resolve_roots():
        if sys.platform.startswith("win") and scope == "user":
            out.append((scope, os.path.join(root, "Support", "Fusion", "Scripts", "Utility")))
        else:
            out.append((scope, os.path.join(root, "Fusion", "Scripts", "Utility")))
    return out


def resolve_installed() -> bool:
    return any(os.path.isdir(root) for _scope, root in resolve_roots())


def file_version(path: str, const: str) -> int:
    """Version écrite dans un script : 0 = fichier absent, 1 = script d'avant le
    versionnage (aucune constante), sinon la valeur de la constante."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return 0
    m = re.search(r"^" + re.escape(const) + r"\s*=\s*(\d+)", text, re.M)
    return int(m.group(1)) if m else 1


def bundled_versions() -> dict:
    """{nom installé : version livrée avec ce PANDORA}."""
    src = _source_dir()
    return {name: file_version(os.path.join(src, source), const)
            for source, name, const in SCRIPTS}


def status() -> dict:
    """État des scripts installés.
    → {"state": "absent" | "outdated" | "ok", "copies": [...], "expected": {...},
       "resolve": bool}"""
    expected = bundled_versions()
    copies = []
    for scope, folder in utility_dirs():
        for _source, name, const in SCRIPTS:
            path = os.path.join(folder, name)
            if os.path.isfile(path):
                copies.append({"scope": scope, "dir": folder, "name": name, "path": path,
                               "version": file_version(path, const)})
    if not copies:
        state = "absent"
    else:
        names = {c["name"] for c in copies}
        stale = any(c["version"] < expected.get(c["name"], 0) for c in copies)
        state = "outdated" if stale or len(names) < len(SCRIPTS) else "ok"
    return {"state": state, "copies": copies, "expected": expected,
            "resolve": resolve_installed()}


def install() -> dict:
    """Copie les deux scripts. Met à jour CHAQUE dossier qui en contient déjà
    (sinon Resolve pourrait lancer l'ancienne copie), sinon installe pour tous
    les utilisateurs, avec repli sur le dossier de l'utilisateur.
    → {"ok", "written": [dossiers], "failed": [(dossier, erreur)], "new": bool,
       "missing_source": str, "no_resolve": bool}"""
    src = _source_dir()
    for source, _name, _const in SCRIPTS:
        if not os.path.isfile(os.path.join(src, source)):
            return {"ok": False, "written": [], "failed": [], "new": False,
                    "missing_source": source, "no_resolve": False}
    if not resolve_installed():
        return {"ok": False, "written": [], "failed": [], "new": False,
                "missing_source": "", "no_resolve": True}

    def copy_into(folder: str):
        os.makedirs(folder, exist_ok=True)
        for source, name, _const in SCRIPTS:
            shutil.copyfile(os.path.join(src, source), os.path.join(folder, name))

    folders = utility_dirs()
    existing = [d for _scope, d in folders
                if any(os.path.isfile(os.path.join(d, name)) for _s, name, _c in SCRIPTS)]
    written, failed = [], []
    for folder in existing:
        try:
            copy_into(folder)
            written.append(folder)
        except OSError as exc:
            failed.append((folder, str(exc)))
    new = not written
    if new:
        for _scope, folder in folders:
            if folder in existing:
                continue
            try:
                copy_into(folder)
                written.append(folder)
                break
            except OSError as exc:
                failed.append((folder, str(exc)))
    return {"ok": bool(written) and not failed, "written": written, "failed": failed,
            "new": new and bool(written), "missing_source": "", "no_resolve": False}
