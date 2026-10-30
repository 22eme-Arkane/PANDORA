"""core/release_notes.py — Les nouveautés de chaque version, lues dans l'application.

Règle Matthieu (27/10/2026) : « désormais à chaque mise à jour de PANDORA », à la
première ouverture ou création d'un projet, une fenêtre montre les nouveautés de
cette version ET des précédentes ; on peut choisir de ne plus l'afficher — jusqu'à
la version suivante, où elle revient d'elle-même.

Les textes vivent dans assets/notes/ (nouveautes_fr.md, whats_new_en.md) : une
section « ## X.Y.Z · AAAA-MM-JJ » par version, la plus récente en tête, en
Markdown. ⚠ À CHAQUE bump de core/version.py, écrire l'entrée FR + EN en tête.

Sans Qt : la fenêtre est ui/dialog_whats_new.
"""
from __future__ import annotations

import os
import re

from core.version import VERSION

FILES = {"fr": "nouveautes_fr.md", "en": "whats_new_en.md"}
#: Version pour laquelle l'utilisateur a coché « Ne plus afficher ».
CONFIG_KEY = "whats_new_hidden"
_HEAD = re.compile(r"^## (\d+(?:\.\d+)+) · (\d{4}-\d{2}-\d{2})[ \t]*$", re.M)
_MONTHS_FR = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
              "septembre", "octobre", "novembre", "décembre")
_MONTHS_EN = ("January", "February", "March", "April", "May", "June", "July", "August",
              "September", "October", "November", "December")

_shown_this_session = False


def notes_dir() -> str:
    from core.paths import assets_root
    return os.path.join(assets_root(), "assets", "notes")


def parse(text: str) -> list[dict]:
    """[{version, date, body}] dans l'ordre du fichier (le plus récent en tête)."""
    heads = list(_HEAD.finditer(text or ""))
    out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        out.append({"version": m.group(1), "date": m.group(2),
                    "body": text[m.end():end].strip()})
    return out


def entries(lang: str | None = None) -> list[dict]:
    """Les nouveautés dans la langue de l'interface (l'autre langue en secours)."""
    if lang is None:
        try:
            from core.i18n import get_lang
            lang = get_lang()
        except Exception:
            lang = "fr"
    order = [lang if lang in FILES else "fr"]
    order += [k for k in FILES if k not in order]
    for key in order:
        try:
            with open(os.path.join(notes_dir(), FILES[key]), encoding="utf-8") as f:
                found = parse(f.read())
        except OSError:
            continue
        if found:
            return found
    return []


def format_date(iso: str, lang: str = "fr") -> str:
    try:
        y, m, d = (int(x) for x in iso.split("-"))
        if lang == "en":
            return f"{_MONTHS_EN[m - 1]} {d}, {y}"
        return f"{'1er' if d == 1 else d} {_MONTHS_FR[m - 1]} {y}"
    except (ValueError, IndexError):
        return iso


def is_hidden(cfg: dict | None = None) -> bool:
    if cfg is None:
        from core.config import load_config
        cfg = load_config()
    return str(cfg.get(CONFIG_KEY) or "") == VERSION


def set_hidden(hidden: bool) -> None:
    """Coche / décoche « Ne plus afficher » pour CETTE version (config entière)."""
    from core.config import load_config, save_config
    cfg = load_config()
    if hidden == is_hidden(cfg):
        return
    if hidden:
        cfg[CONFIG_KEY] = VERSION
    else:
        cfg.pop(CONFIG_KEY, None)
    save_config(cfg)


def should_show() -> bool:
    """Vrai une fois par session, tant que cette version n'est pas masquée."""
    if _shown_this_session:
        return False
    try:
        return not is_hidden() and bool(entries())
    except Exception:
        return False


def mark_shown() -> None:
    global _shown_this_session
    _shown_this_session = True
