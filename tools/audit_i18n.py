"""Audit i18n : trouve les strings français dans les fichiers UI non couverts par _FR_TO_EN."""
import re, ast, sys
from pathlib import Path

root = Path(__file__).parent.parent

# Extraire les clés de _FR_TO_EN via regex (évite d'importer les dépendances Qt)
i18n_src = (root / "core" / "i18n.py").read_text(encoding="utf-8")
fr_to_en = {}
for m in re.finditer(r'"((?:[^"\\]|\\.)*)"\s*:\s*"((?:[^"\\]|\\.)*)"', i18n_src):
    fr_to_en[m.group(1).replace('\\n', '\n')] = m.group(2).replace('\\n', '\n')
known = set(fr_to_en.keys())

print(f"_FR_TO_EN chargé : {len(known)} entrées")

FRENCH_RE = re.compile(r'[àâäéèêëîïôùûüçœæÀÂÄÉÈÊËÎÏÔÙÛÜÇŒÆ]')

SKIP_FRAGMENTS = [
    '\\', '/', '.py', 'http', '#', 'bytedance', 'fal_client',
    'fal.ai/', 'seedance', 'Seedance', 'anthropic', 'nano_banana',
    '.json', '.png', '.jpg', '.mp4', 'PANDORA/', 'Videos/',
    'utf-8', 'win32', '%localappdata', 'AppData',
]

ui_files = (
    sorted((root / "ui").glob("*.py")) +
    sorted((root / "api").glob("*.py")) +
    sorted((root / "core").glob("*.py"))
)

missing = {}

for fpath in ui_files:
    src = fpath.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        continue

    file_missing = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
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
        display = s.replace('\n', '\\n')[:130]
        lines.append(f"  L{lineno:4d}  {repr(s.replace(chr(10), '\\n'))[:130]}")
        total += 1

lines.append(f"\n\nTOTAL MANQUANTS : {total} strings dans {len(missing)} fichiers")
out.write_text('\n'.join(lines), encoding='utf-8')
print(f"Résultat écrit dans {out}")
print(f"TOTAL MANQUANTS : {total} strings dans {len(missing)} fichiers")
