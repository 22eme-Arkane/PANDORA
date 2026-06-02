"""Audit i18n : trouve les strings français dans les fichiers UI non couverts par _FR_TO_EN."""
import re, ast, sys
from pathlib import Path

root = Path(__file__).parent.parent

# Charge les clés depuis le vrai dictionnaire (core.i18n n'a pas de dépendance Qt)
import sys as _sys
_sys.path.insert(0, str(root))
from core.i18n import _FR_TO_EN
known = set(_FR_TO_EN.keys())

print(f"_FR_TO_EN chargé : {len(known)} entrées")

FRENCH_RE = re.compile(r'[àâäéèêëîïôùûüçœæÀÂÄÉÈÊËÎÏÔÙÛÜÇŒÆ]')

SKIP_FRAGMENTS = [
    '\\', '/', '.py', 'http', '#', 'bytedance', 'fal_client',
    'fal.ai/', 'seedance', 'Seedance', 'anthropic', 'nano_banana',
    '.json', '.png', '.jpg', '.mp4', 'PANDORA/', 'Videos/',
    'utf-8', 'win32', '%localappdata', 'AppData',
]

# Fichiers exclus : ils gèrent leur propre traduction (système bilingue dédié)
# et ne passent donc pas par _FR_TO_EN.
SKIP_FILES = {"dialog_user_manual.py"}

ui_files = [
    p for p in (
        sorted((root / "ui").glob("*.py")) +
        sorted((root / "api").glob("*.py")) +
        sorted((root / "core").glob("*.py"))
    )
    if p.name not in SKIP_FILES
]

missing = {}

for fpath in ui_files:
    src = fpath.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        continue

    # Repère les docstrings (module / fonction / classe) pour les ignorer :
    # ce ne sont pas des chaînes d'interface.
    docstring_ids = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(n, "body", None)
            if body and isinstance(body[0], ast.Expr) and \
               isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                docstring_ids.add(id(body[0].value))

    file_missing = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstring_ids:
                continue
            s = node.value
            if not FRENCH_RE.search(s):
                continue
            if len(s.strip()) <= 3:
                continue
            if any(x in s for x in SKIP_FRAGMENTS):
                continue
            if s not in known:
                file_missing.append((node.lineno, s))

    if file_missing:
        missing[fpath.relative_to(root)] = file_missing

out = root / "tools" / "audit_i18n_result.txt"
total = 0
lines = []
for fpath, items in missing.items():
    lines.append(f"\n{'='*60}")
    lines.append(f"  {fpath}")
    lines.append(f"{'='*60}")
    for lineno, s in items:
        display = repr(s.replace(chr(10), '\\n'))[:130]
        lines.append(f"  L{lineno:4d}  {display}")
        total += 1

lines.append(f"\n\nTOTAL MANQUANTS : {total} strings dans {len(missing)} fichiers")
out.write_text('\n'.join(lines), encoding='utf-8')
print(f"Résultat écrit dans {out}")
print(f"TOTAL MANQUANTS : {total} strings dans {len(missing)} fichiers")
