"""tools/update_aiodos_client.py — Rafraîchir la copie du client AIODOS (aiodos_client/).

PANDORA parle à l'AIODOS INSTALLÉ (qui se met à jour seul) avec le client officiel
aiodos-client (Apache-2.0, sans dépendance, pas encore sur PyPI), copié dans
aiodos_client/ avec sa LICENSE et sa NOTICE. Le client lit ce qu'AIODOS annonce
(`features`) : une nouvelle version d'AIODOS ne casse rien, et ses nouvelles
fonctions arrivent dans PANDORA avec une nouvelle copie du client — ce script.

    python tools/update_aiodos_client.py [dépôt AIODOS]   (défaut : ..\\..\\AIODOS)

Puis : les deux harnais (tools/test_cinema.py, tools/test_live.py) — le test
« aiodos_mes_machines » tourne contre le faux AIODOS du client lui-même.
"""
import filecmp
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(HERE, "aiodos_client")


def main() -> int:
    repo = os.path.abspath(sys.argv[1] if len(sys.argv) > 1
                           else os.path.join(HERE, "..", "..", "AIODOS"))
    src_root = os.path.join(repo, "clients", "python")
    src = os.path.join(src_root, "src", "aiodos_client")
    if not os.path.isfile(os.path.join(src, "__init__.py")):
        print(f"Client AIODOS introuvable : {src}")
        return 1

    def version(folder):
        try:
            with open(os.path.join(folder, "__init__.py"), encoding="utf-8") as f:
                m = re.search(r'__version__\s*=\s*"([^"]+)"', f.read())
            return m.group(1) if m else "?"
        except OSError:
            return "aucune"

    before, after = version(DEST), version(src)
    os.makedirs(DEST, exist_ok=True)
    changed = []
    wanted = {n for n in os.listdir(src) if n.endswith(".py")}
    for name in sorted(wanted):
        a, b = os.path.join(src, name), os.path.join(DEST, name)
        if not (os.path.isfile(b) and filecmp.cmp(a, b, shallow=False)):
            shutil.copyfile(a, b)
            changed.append(name)
    for name in ("LICENSE", "NOTICE"):
        a, b = os.path.join(src_root, name), os.path.join(DEST, name)
        if os.path.isfile(a) and not (os.path.isfile(b) and filecmp.cmp(a, b, shallow=False)):
            shutil.copyfile(a, b)
            changed.append(name)
    gone = sorted(n for n in os.listdir(DEST) if n.endswith(".py") and n not in wanted)
    print(f"aiodos-client {before} → {after} : {len(changed)} fichier(s) mis à jour"
          + (f" ({', '.join(changed)})" if changed else ""))
    if gone:
        print("Fichiers qui n'existent plus dans le client (à retirer à la main, après "
              "vérification) : " + ", ".join(gone))
    return 0


if __name__ == "__main__":
    sys.exit(main())
