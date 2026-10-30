"""tools/update_arklight_engine.py — Rafraîchir la copie du moteur 3D d'ARKLIGHT (arklight_engine/).

Demande Matthieu (29/10/2026) : l'onglet « 3D » de PANDORA (lumière, mise en scène,
décor) reprend le plan de feu d'ARKLIGHT PC. ARKLIGHT et PANDORA ont le même auteur,
qui place la reprise sous Apache 2.0 (ARKLIGHT passe aussi en Apache 2.0).

PANDORA reprend À L'IDENTIQUE la partie « scène » de l'interface web d'ARKLIGHT : la
vue 3D (projecteurs, faisceaux, grip, décor, mannequins), le plan de feu 2D, le magasin
d'état de l'interface et les modules partagés (bibliothèque de projecteurs, filtres,
modificateurs, accessoires). Le script part de quelques points d'entrée et suit les
`import` de module en module : seuls les fichiers réellement atteints sont copiés
(ni la console DMX, ni le MIDI, ni le serveur Node, ni Electron). three.js est repris
de node_modules (licence MIT).

Le reste (pont avec PANDORA, frise temporelle, caméra du plan, capture) est propre à
PANDORA : scene3d_web/ et core/scene3d/. Le dépôt d'ARKLIGHT n'est JAMAIS modifié.

    python tools/update_arklight_engine.py [dépôt ARKLIGHT PC]   (défaut : ..\\..\\ARKLIGHT PC)

Puis : les deux harnais (tools/test_cinema.py, tools/test_live.py).
"""
import filecmp
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(HERE, "arklight_engine")

#: Points d'entrée (chemins d'URL, tels que la page les charge).
ENTRIES = (
    "/js/store.js",
    "/js/viewport/viewport.js",
    "/js/plot/plot-view.js",
    "/js/i18n.js",
    "/shared/fixtures/index.js",
    "/shared/objects.js",
    "/shared/props.js",
    "/shared/grip.js",
    "/shared/plans.js",
    "/shared/mvr.js",
    "/vendor/three/examples/jsm/exporters/GLTFExporter.js",
    # Inspecteur complet des projecteurs, menus embarqués simulés (faces avant), console
    # « Canaux » et actions de la sélection (Matthieu 30/10/2026 : « les mêmes réglages
    # que l'inspecteur d'ARKLIGHT, avec les simulations et les menus des projecteurs »)
    "/js/ui/inspector.js",
    "/js/ui/control-panel.js",
    "/js/ui/console-control.js",
    "/js/actions.js",
    # Personnages animés du Plan de feu (scene3d_web/characters.js, 29/10/2026)
    "/vendor/three/examples/jsm/loaders/GLTFLoader.js",
    "/vendor/three/examples/jsm/utils/SkeletonUtils.js",
)
#: Fichiers repris en plus des modules (feuille de style de la vue et du plan).
EXTRA = ("/css/app.css",)

# Instructions en tête de ligne (le code d'ARKLIGHT est formaté par Prettier) : une
# chaîne traduite qui contient « export » n'est pas une instruction.
_IMPORT = re.compile(
    r"""^\s*(?:import|export)\s*(?:[\w*{}\s,$]+?\s*from\s*)?['"]([^'"]+)['"]"""
    r"""|\bimport\(\s*['"]([^'"]+)['"]\s*\)""", re.M)


def _url_to_src(repo: str, url: str) -> str:
    """Chemin d'URL (comme le serveur d'ARKLIGHT le sert) -> fichier du dépôt."""
    if url.startswith("/vendor/three/"):
        return os.path.join(repo, "node_modules", "three", *url[len("/vendor/three/"):].split("/"))
    if url.startswith("/shared/"):
        return os.path.join(repo, "shared", *url[len("/shared/"):].split("/"))
    return os.path.join(repo, "web", *url.lstrip("/").split("/"))


def _resolve(spec: str, from_url: str) -> str | None:
    if spec == "three":
        return "/vendor/three/build/three.module.js"
    if spec.startswith("three/addons/"):
        return "/vendor/three/examples/jsm/" + spec[len("three/addons/"):]
    if spec.startswith("/"):
        return spec
    if spec.startswith("."):
        parts = from_url.split("/")[:-1]
        for p in spec.split("/"):
            if p == "..":
                if len(parts) > 1:   # comme le navigateur : on ne remonte pas au-dessus de la racine
                    parts.pop()
            elif p not in (".", ""):
                parts.append(p)
        return "/".join(parts)
    return None   # module nu (node:…, ws…) : refusé plus bas


def closure(repo: str) -> tuple[list[str], list[str]]:
    """Fichiers atteints depuis ENTRIES (chemins d'URL), et problèmes rencontrés."""
    seen, todo, issues = set(), list(ENTRIES), []
    while todo:
        url = todo.pop()
        if url in seen:
            continue
        seen.add(url)
        src = _url_to_src(repo, url)
        if not os.path.isfile(src):
            issues.append(f"introuvable : {url}")
            continue
        with open(src, encoding="utf-8") as f:
            code = f.read()
        # les commentaires peuvent citer « import … from '…' » : on les retire d'abord
        code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
        code = re.sub(r"(?m)^\s*//.*$", "", code)
        for m in _IMPORT.finditer(code):
            spec = m.group(1) or m.group(2)
            dep = _resolve(spec, url)
            if dep is None:
                issues.append(f"{url} importe « {spec} » (module Node ou paquet nu)")
            elif dep not in seen:
                todo.append(dep)
    return sorted(seen | set(EXTRA)), issues


def _dest(url: str) -> str:
    return os.path.join(DEST, *url.lstrip("/").split("/"))


def _git(repo: str, *args) -> str:
    try:
        return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                              timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def main() -> int:
    repo = os.path.abspath(sys.argv[1] if len(sys.argv) > 1
                           else os.path.join(HERE, "..", "..", "ARKLIGHT PC"))
    if not os.path.isfile(os.path.join(repo, "web", "js", "viewport", "viewport.js")):
        print(f"ARKLIGHT PC introuvable : {repo}")
        return 1
    urls, issues = closure(repo)
    if issues:
        print("Copie refusée :\n  " + "\n  ".join(issues))
        return 1
    with open(os.path.join(repo, "package.json"), encoding="utf-8") as f:
        pkg = json.load(f)
    with open(os.path.join(repo, "node_modules", "three", "package.json"), encoding="utf-8") as f:
        three = json.load(f).get("version", "?")

    changed, files = [], {}
    for url in urls:
        a, b = _url_to_src(repo, url), _dest(url)
        os.makedirs(os.path.dirname(b), exist_ok=True)
        if not (os.path.isfile(b) and filecmp.cmp(a, b, shallow=False)):
            shutil.copyfile(a, b)
            changed.append(url)
        with open(b, "rb") as f:
            files[url] = hashlib.sha256(f.read()).hexdigest()[:16]
    lic = os.path.join(repo, "node_modules", "three", "LICENSE")
    shutil.copyfile(lic, os.path.join(DEST, "vendor", "three", "LICENSE"))

    # fichiers qui ne sont plus atteints : signalés (jamais effacés par le script)
    stale = []
    for root, _dirs, names in os.walk(DEST):
        for n in names:
            rel = "/" + os.path.relpath(os.path.join(root, n), DEST).replace(os.sep, "/")
            if rel.endswith((".js", ".css")) and rel not in files:
                stale.append(rel)

    manifest = {
        "arklight": pkg.get("version", "?"),
        "commit": _git(repo, "rev-parse", "--short", "HEAD"),
        "modifie": bool(_git(repo, "status", "--porcelain", "--", "web", "shared")),
        "three": three,
        "fichiers": files,
    }
    path = os.path.join(DEST, "manifest.json")
    old = None
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            old = json.load(f)
    if old != manifest:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
    size = sum(os.path.getsize(_dest(u)) for u in urls)
    print(f"Moteur ARKLIGHT {old.get('arklight') if old else 'aucun'} -> {manifest['arklight']}"
          f" (three.js {three}) : {len(urls)} fichiers, {size / 1e6:.1f} Mo,"
          f" {len(changed)} mis à jour")
    if stale:
        print("Plus atteints (à retirer à la main si voulu) :\n  " + "\n  ".join(stale))
    return 0


if __name__ == "__main__":
    sys.exit(main())
