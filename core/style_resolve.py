"""core/style_resolve.py — quel style visuel un plan doit-il VRAIMENT porter ?

Le style visuel est capturé une fois, à la création du storyboard, et cuit dans
la section `[🎨 STYLE VISUEL]` de chaque plan. Rien ne le rafraîchit ensuite :
c'est voulu — un style retouché plan par plan ne doit pas être écrasé par le
style du projet.

Mais cette immutabilité a figé une TRONCATURE. La note de réalisation de FIGHTER
tient en treize lignes (référence Arcane, chiaroscuro, character design, fumée
volumétrique, néons…) ; la capture n'en a gardé qu'une seule, « Rendu 3D
painterly… », parce que la section « STYLE VISUEL » de la note était lue au
mauvais endroit. Les soixante-quinze plans du projet portent donc une ligne sur
treize, et le Mood — qui préfère la section cuite au style relu en direct —
propage la perte jusqu'à l'image. Le moteur n'a jamais reçu la consigne
« Arcane » : d'où des rendus photoréalistes (constat Matthieu 2026-07-31).

D'où l'arbitrage de ce module, en une phrase : **on répare une troncature, on
ne touche jamais à une réécriture.** Si tout ce que dit le texte cuit se
retrouve dans le style courant, c'est un extrait appauvri — on rend la version
complète. Si le texte cuit dit autre chose, c'est un choix de réalisation — on
le laisse intact.
"""

import re
import unicodedata


def _norm_line(s: str) -> str:
    """Ligne comparable : sans accents, sans puce, sans casse ni ponctuation
    faible. Deux écritures d'une même intention doivent se reconnaître."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.strip().lstrip("-•*·—–").strip()
    s = re.sub(r"[\s]+", " ", s)
    return s.strip(" .;,:").lower()


def _lines(text: str) -> list:
    """Lignes utiles d'un bloc de style (les vides et les titres sautent)."""
    out = []
    for raw in (text or "").replace("\r", "").split("\n"):
        n = _norm_line(raw)
        if n and not n.startswith("#"):
            out.append(n)
    return out


def is_truncation_of(baked: str, full: str) -> bool:
    """`baked` est-il un simple EXTRAIT appauvri de `full` ?

    Vrai quand le texte cuit est plus court ET que chacune de ses lignes se
    retrouve dans le style complet. Une ligne réécrite à la main suffit à
    répondre faux : on ne réécrit pas le travail de l'utilisateur.
    """
    b, f = _lines(baked), _lines(full)
    if not b or not f:
        return False
    if len(b) >= len(f):
        return False
    _hay = "\n".join(f)
    return all((line in f) or (line in _hay) for line in b)


def effective_visual_style(baked: str, current: str) -> str:
    """Le style à utiliser réellement pour ce plan.

    · pas de style cuit           → le style courant du projet ;
    · style cuit = extrait tronqué → le style courant, COMPLET (réparation) ;
    · style cuit différent         → il est respecté tel quel (édition assumée).
    """
    _b = (baked or "").strip()
    _c = (current or "").strip()
    if not _b:
        return _c
    if not _c:
        return _b
    return _c if is_truncation_of(_b, _c) else _b
