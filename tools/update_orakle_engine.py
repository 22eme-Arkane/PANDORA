"""tools/update_orakle_engine.py — Rafraîchir la copie du moteur d'ORAKLE (orakle_engine/).

Demande Matthieu (27/10/2026) : la dictée d'ORAKLE dans tous les champs de texte de
PANDORA, avec un moteur EMBARQUÉ (PANDORA dicte même sans ORAKLE installé). PANDORA
reprend donc, à l'identique, les deux modules d'ORAKLE qui ne dépendent de rien
d'autre que numpy, sounddevice et faster-whisper :

    recorder.py      capture du micro (mono 16 kHz, flux « chaud »)
    transcriber.py   Whisper local (repli CPU, détection de langue restreinte)

Le reste (raccourci, injection au curseur, fenêtre, réglages) est propre à
PANDORA : ui/dictation.py et core/dictation.py. Le dépôt d'ORAKLE n'est JAMAIS
modifié par ce script.

    python tools/update_orakle_engine.py [dépôt ORAKLE]   (défaut : ..\\..\\ORAKLE)

Puis : les deux harnais (tools/test_cinema.py, tools/test_live.py).
"""
import filecmp
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(HERE, "orakle_engine")
#: Les modules repris tels quels (aucun import d'ORAKLE dedans).
MODULES = ("recorder.py", "transcriber.py")


def _version(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            m = re.search(r'VERSION\s*=\s*"([^"]+)"', f.read())
        return m.group(1) if m else "?"
    except OSError:
        return "aucune"


def main() -> int:
    repo = os.path.abspath(sys.argv[1] if len(sys.argv) > 1
                           else os.path.join(HERE, "..", "..", "ORAKLE"))
    src = os.path.join(repo, "orakle")
    if not all(os.path.isfile(os.path.join(src, m)) for m in MODULES):
        print(f"Moteur d'ORAKLE introuvable : {src}")
        return 1
    for name in MODULES:
        with open(os.path.join(src, name), encoding="utf-8") as f:
            code = f.read()
        if re.search(r"^\s*(from\s+(orakle|\.)|import\s+orakle)", code, re.M):
            print(f"{name} importe désormais d'autres modules d'ORAKLE : copie à revoir à la main.")
            return 1

    before = _version(os.path.join(DEST, "__init__.py"))
    after = _version(os.path.join(src, "version.py"))
    os.makedirs(DEST, exist_ok=True)
    changed = []
    for name, a in [(m, os.path.join(src, m)) for m in MODULES] + [
            ("LICENSE", os.path.join(repo, "LICENSE"))]:
        b = os.path.join(DEST, name)
        if not (os.path.isfile(b) and filecmp.cmp(a, b, shallow=False)):
            shutil.copyfile(a, b)
            changed.append(name)
    init = os.path.join(DEST, "__init__.py")
    with open(init, encoding="utf-8") as f:
        text = f.read()
    new = re.sub(r'VERSION\s*=\s*"[^"]*"', f'VERSION = "{after}"', text, count=1)
    if new != text:
        with open(init, "w", encoding="utf-8", newline="\n") as f:
            f.write(new)
        changed.append("__init__.py")
    print(f"Moteur ORAKLE {before} -> {after} : {len(changed)} fichier(s) mis à jour"
          + (f" ({', '.join(changed)})" if changed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
