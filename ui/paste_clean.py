"""ui/paste_clean.py — Coller du texte sans son fond blanc.

Constat Matthieu (27/10/2026) : « quand je copie un texte depuis un navigateur ou
un éditeur de texte dans PANDORA, un fond blanc apparaît ». Le HTML copié porte
ses couleurs (fond blanc, texte noir) et un QTextEdit les garde telles quelles,
illisibles sur le fond sombre.

- `install()` (main.py, avant le premier widget) : tout collage dans un QTextEdit
  passe par `clean_html` — fonds et couleurs de texte retirés, le reste gardé
  (gras, italique, souligné, police, titres, listes).
- `strip_colors(edit)` : le bouton « Retirer le fond » des outils de texte, si un
  texte déjà collé garde ses couleurs (sélection, sinon tout le document).
"""
from __future__ import annotations

import re

from PyQt6.QtCore import QMimeData
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QTextEdit

#: background / background-color / color dans un attribut style="…".
_STYLE_COLORS = re.compile(r"(?i)(?<![-\w])(?:background(?:-color)?|color)\s*:\s*[^;\"']*;?")
#: Anciens attributs HTML : bgcolor="…", color="…" (balise <font>).
_ATTR_COLORS = re.compile(r"(?i)\s(?:bgcolor|color)\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)")


def clean_html(html: str) -> str:
    """Le HTML collé sans aucun fond ni couleur de texte."""
    return _ATTR_COLORS.sub("", _STYLE_COLORS.sub("", html or ""))


_orig_insert = None


def _clean_insert(self, source):
    try:
        if source is not None and source.hasHtml():
            clean = QMimeData()
            clean.setHtml(clean_html(source.html()))
            if source.hasText():
                clean.setText(source.text())
            return _orig_insert(self, clean)
    except Exception:
        pass
    return _orig_insert(self, source)


def install() -> bool:
    """Branche le nettoyage sur le collage de tous les QTextEdit (une fois)."""
    global _orig_insert
    if _orig_insert is not None:
        return True
    _orig_insert = QTextEdit.insertFromMimeData
    QTextEdit.insertFromMimeData = _clean_insert
    return True


def strip_colors(edit: QTextEdit) -> None:
    """Retire fonds et couleurs de texte de la sélection (ou de tout le texte),
    en une seule étape annulable."""
    doc = edit.document()
    sel = edit.textCursor()
    start, end = (sel.selectionStart(), sel.selectionEnd()) if sel.hasSelection() \
        else (0, doc.characterCount() - 1)
    cur = QTextCursor(doc)
    cur.beginEditBlock()
    try:
        block = doc.findBlock(start)
        while block.isValid() and block.position() <= end:
            bfmt = block.blockFormat()
            if bfmt.background().style().value:
                bfmt.clearBackground()
                c = QTextCursor(block)
                c.setBlockFormat(bfmt)
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    a = max(start, frag.position())
                    b = min(end, frag.position() + frag.length())
                    if a < b:
                        fmt = frag.charFormat()
                        fmt.clearBackground()
                        fmt.clearForeground()
                        c = QTextCursor(doc)
                        c.setPosition(a)
                        c.setPosition(b, QTextCursor.MoveMode.KeepAnchor)
                        c.setCharFormat(fmt)
                it += 1
            block = block.next()
    finally:
        cur.endEditBlock()
