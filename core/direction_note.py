"""Note de réalisation attachée à un scénario Cinéma.

La note conserve les intentions de fabrication qui ne doivent jamais être injectées
dans le texte narratif : style, temporalité, rythme, durée des plans, grammaire
caméra, continuité et son. Elle est volontairement stockée comme texte structuré :
elle reste lisible et modifiable par l'humain, tout en pouvant être transmise telle
quelle au moteur de découpage.
"""

from __future__ import annotations

import re
import unicodedata


SECTIONS = (
    "INTENTION GÉNÉRALE",
    "STYLE VISUEL",
    "TEMPORALITÉ ET LUMIÈRE",
    "RYTHME ET MONTAGE",
    "DURÉE DES PLANS",
    "GRAMMAIRE CAMÉRA",
    "CONTINUITÉ",
    "SON ET MUSIQUE",
    "CONTRAINTES ET NOTES LIBRES",
)


def empty_note() -> str:
    """Gabarit humain d'une nouvelle note, sans inventer d'intention."""
    return "\n\n".join(f"## {title}\n" for title in SECTIONS).rstrip() + "\n"


def normalize_note(value) -> str:
    """Accepte l'ancien texte libre ou un futur objet structuré sans perdre de données."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        blocks = []
        for title in SECTIONS:
            key = title.lower().replace(" ", "_").replace("é", "e").replace("è", "e")
            text = str(value.get(key, "") or "").strip()
            blocks.append(f"## {title}\n{text}")
        free = str(value.get("notes", "") or "").strip()
        if free:
            blocks.append(f"## NOTES COMPLÉMENTAIRES\n{free}")
        return "\n\n".join(blocks).strip()
    return ""


def note_for_ai(value) -> str:
    """Retourne uniquement la note utile ; un gabarit encore vide devient vide."""
    text = normalize_note(value)
    meaningful = [line.strip() for line in text.splitlines()
                  if line.strip() and not line.lstrip().startswith("##")]
    return text if meaningful else ""


def section_text(value, title: str) -> str:
    """Contenu (sans l'en-tête) d'une section de la note, ex. « STYLE VISUEL ».

    Reconnaît les en-têtes « ## Titre » (tolérant : accents, casse, niveau de #).
    Renvoie le texte jusqu'à la section suivante, vidé du gabarit ; « » si absente
    ou vide. Sert à alimenter le style visuel des prompts storyboard depuis la note
    de réalisation (demande Matthieu 2026-07-24)."""
    text = normalize_note(value)
    if not text:
        return ""

    def _norm(s: str) -> str:
        s = unicodedata.normalize("NFD", s or "")
        s = "".join(c for c in s if not unicodedata.combining(c))
        return " ".join(s.upper().split())

    want = _norm(title)
    lines = text.splitlines()
    out: list[str] = []
    capturing = False
    heading = re.compile(r"^\s*#{1,6}\s*(?P<title>.+?)\s*$")
    for line in lines:
        m = heading.match(line)
        if m:
            if capturing:                       # section suivante → stop
                break
            if _norm(m.group("title")) == want:
                capturing = True
            continue
        if capturing:
            out.append(line)
    return "\n".join(out).strip()


def extract_from_analysis(analysis: str) -> str:
    """Extrait la section consacrée à la note depuis une analyse dramaturgique.

    Le prompt d'analyse impose une section 6 puis un inventaire en section 7. Cette
    extraction est volontairement déterministe : les intentions déjà produites par
    l'IA sont rangées sans nouvel appel API et sans risquer de copier l'inventaire
    des personnages dans la note de réalisation.
    """
    text = (analysis or "").strip()
    if not text:
        return ""

    lines = text.splitlines()
    start = None
    heading_level = 0
    section_heading = re.compile(
        r"^\s*(?P<marks>#{0,6})\s*(?:section\s+)?6\s*[.\):\-–—]?\s*(?P<title>.*)$",
        re.IGNORECASE,
    )
    note_words = ("note de réalisation", "note de realisation", "director's note",
                  "directors note", "director note")
    for index, line in enumerate(lines):
        match = section_heading.match(line)
        if not match:
            continue
        title = match.group("title").strip().casefold()
        if any(word in title for word in note_words):
            start = index + 1
            heading_level = len(match.group("marks") or "")
            break
    if start is None:
        return ""

    next_numbered = re.compile(
        r"^\s*#{0,6}\s*(?:section\s+)?(?P<number>\d+)\s*[.\):\-–—]",
        re.IGNORECASE,
    )
    end = len(lines)
    for index in range(start, len(lines)):
        stripped = lines[index].strip()
        match = next_numbered.match(stripped)
        if match and int(match.group("number")) > 6:
            end = index
            break
        if heading_level and stripped.startswith("#"):
            marks = len(stripped) - len(stripped.lstrip("#"))
            if marks and marks <= heading_level:
                end = index
                break

    body = "\n".join(lines[start:end]).strip()
    return body


def append_to_note(current: str, addition: str, content: str | None = None,
                   replace: bool = False) -> str:
    """Ajoute une intention sans écraser l'écriture humaine.

    Avec ``content``, ``addition`` est le titre d'une section. ``replace=True``
    met à jour cette seule section, ce qui permet de relancer une analyse visuelle
    sans empiler plusieurs versions du même moodboard.
    """
    base = normalize_note(current)
    if content is not None:
        title = (addition or "").strip().upper()
        body = (content or "").strip()
        extra = f"## {title}\n{body}" if title and body else body
        if replace and title and base:
            marker = f"## {title}"
            start = base.find(marker)
            if start >= 0:
                next_section = base.find("\n## ", start + len(marker))
                end = len(base) if next_section < 0 else next_section
                return (base[:start].rstrip() + "\n\n" + extra + "\n\n"
                        + base[end:].lstrip()).strip() + "\n"
    else:
        extra = (addition or "").strip()
    if not extra:
        return base
    if not base:
        base = empty_note().rstrip()
    if extra in base:
        return base
    return base.rstrip() + "\n\n" + extra + "\n"
