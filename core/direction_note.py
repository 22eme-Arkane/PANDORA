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
    de réalisation (demande Matthieu 2026-07-24).

    ⚠ Une note porte SOUVENT le titre DEUX FOIS : le gabarit vide créé par
    `empty_note()` en tête, puis la vraie section ajoutée plus bas (l'analyse
    empile ses intentions à la suite au lieu de remplir le gabarit). On
    parcourt donc TOUTES les occurrences et on renvoie la PREMIÈRE NON VIDE —
    sinon un gabarit vide masque le contenu réel (bug constaté le 2026-07-31
    sur FIGHTER v2 : « ## STYLE VISUEL » vide en position 22, la vraie section
    en position 2560 ; le style tombait alors dans le repli, qui ne ramassait
    qu'une seule puce sur six)."""
    text = normalize_note(value)
    if not text:
        return ""

    def _norm(s: str) -> str:
        s = unicodedata.normalize("NFD", s or "")
        s = "".join(c for c in s if not unicodedata.combining(c))
        return " ".join(s.upper().split())

    want = _norm(title)
    lines = text.splitlines()
    heading = re.compile(r"^\s*#{1,6}\s*(?P<title>.+?)\s*$")
    blocks: list[str] = []
    out: list[str] = []
    capturing = False
    for line in lines:
        m = heading.match(line)
        if m:
            if capturing:                       # section suivante → on solde
                blocks.append("\n".join(out).strip())
                out, capturing = [], False
            if _norm(m.group("title")) == want:
                capturing = True
            continue
        if capturing:
            out.append(line)
    if capturing:                               # section en fin de note
        blocks.append("\n".join(out).strip())
    return next((b for b in blocks if b), "")


def _sans_markdown(s: str) -> str:
    """Retire le gras/italique markdown des sorties IA (**…**, __…__)."""
    return re.sub(r"\*\*|__", "", s or "").strip()


# Lignes qui DÉCLARENT un style visuel (utile quand l'Analyse range le style dans
# « INTENTIONS ISSUES DE L'ANALYSE » plutôt que dans la section « STYLE VISUEL »).
_STYLE_DECL_RE = re.compile(
    r"(style\s+graphique|style\s+d['’]image|style\s+visuel|style\s+d['’]animation|"
    r"rendu\s+\w+|palette|look\s+visuel)",
    re.IGNORECASE,
)


# Lignes de PRODUCTION qui traînent dans un paragraphe de style et n'ont rien à
# faire dans un prompt d'image (« Durées : 6-8s », « Format : 16:9 »…). On ne
# juge PAS le contenu, seulement le libellé : un couple « métadonnée : valeur »
# est une consigne de fabrication, pas une intention visuelle. La lumière,
# elle, reste du style et passe.
_HORS_STYLE_RE = re.compile(
    r"^\s*(dur[ée]es?|timings?|rythmes?|cadences?|budgets?|fps|"
    r"r[ée]solutions?|formats?|livrables?|nombre\s+de\s+plans?|"
    r"nb\s+de\s+plans?)\s*:",
    re.IGNORECASE,
)


def _declare_un_style(line: str) -> bool:
    """La ligne ANNONCE-t-elle un parti pris visuel ?

    Le markdown IA (« **Style d'image :** ») est nettoyé AVANT tout : lstrip
    mangeait les ** ouvrants et laissait le « :** » fermant partir au moteur en
    fragment cassé (constat Matthieu 2026-07-28, projet FIGHTER)."""
    s = _sans_markdown((line or "").strip().lstrip("-•*").strip()).lower()
    return bool(s) and (s.startswith("style ") or bool(_STYLE_DECL_RE.search(s)))


def _blocs_de_note(text: str) -> list:
    """Découpe la note en BLOCS : une ligne vide ou un titre les sépare.

    C'est l'unité qui compte pour lire une note : un paragraphe de style se
    présente comme une phrase d'accroche suivie de ses puces, sans ligne vide
    entre elles."""
    blocs, cur = [], []
    for raw in (text or "").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            if cur:
                blocs.append(cur)
                cur = []
            continue
        cur.append(raw)
    if cur:
        blocs.append(cur)
    return blocs


def visual_style_from_note(value) -> str:
    """Style visuel décrit dans la note de réalisation, de façon TOLÉRANTE :
    1) le contenu de la section « STYLE VISUEL » s'il est renseigné ;
    2) sinon, le ou les BLOCS qui parlent de style ailleurs dans la note (ex. le
       paragraphe rangé par l'Analyse sous « INTENTIONS ISSUES DE L'ANALYSE DU
       SCÉNARIO »).
    Chaîne vide si rien trouvé. Ne lève jamais.

    ⚠ Le repli travaillait LIGNE À LIGNE et ne gardait que celles contenant un
    mot déclencheur (« rendu », « palette », « style »…). Sur une note rédigée
    en puces DESCRIPTIVES, une seule ligne passait : sur la note de FIGHTER,
    « Rendu 3D painterly » survivait, et Arcane, le chiaroscuro, le character
    design, la fumée volumétrique et les néons étaient perdus — le moteur ne
    recevait jamais le style demandé. On raisonne donc par BLOC : dès qu'une
    ligne d'un paragraphe déclare un style, c'est que le paragraphe entier en
    parle, et il part en entier. Les blocs voisins (temporalité, son, intention)
    restent à l'écart, puisqu'ils n'ont aucune ligne déclarative."""
    try:
        sec = section_text(value, "STYLE VISUEL").strip()
        if sec:
            return sec
        hits: list[str] = []
        for bloc in _blocs_de_note(normalize_note(value)):
            if not any(_declare_un_style(l) for l in bloc):
                continue
            for raw in bloc:
                item = _sans_markdown(raw.strip().lstrip("-•*").strip())
                if not item:
                    continue
                # Métadonnée de fabrication glissée dans le paragraphe.
                if _HORS_STYLE_RE.match(item):
                    continue
                # Libellé NU (« Style d'image : ») : il n'apporte rien au moteur,
                # le contenu est dans les lignes qui suivent — déjà capturées
                # puisqu'on prend tout le bloc.
                _avant, _sep, _apres = item.partition(":")
                if _sep and not _apres.strip():
                    continue
                hits.append(item)
        return "\n".join(hits).strip()
    except Exception:
        return ""


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
