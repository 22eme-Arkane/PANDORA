"""ui/themes.py — Les thèmes de couleur de PANDORA, au choix dans les Paramètres.

Demande Matthieu (27/10/2026) : « changer la couleur de l'interface et avoir le
choix dans les paramètres : quelque chose de plus noir et doré, garder le bleu
sombre actuel, et d'autres propositions, plus vives, plus colorées ».

Un thème = une palette `CP` (mêmes clés que ui/styles) + quelques couleurs
dérivées : survols des deux accents, texte posé sur l'accent, onglet actif de la
barre, et la teinte des badges d'icônes.

Le piège : l'interface ne lit pas que `CP`. Quelque 600 couleurs du thème
d'origine sont écrites EN DUR dans les feuilles de style (« rgba(78,205,196,…) »
pour les fonds teintés de l'accent, « #6eded6 » pour ses survols, « #07080f »
pour le texte sur les boutons…). Plutôt que de retoucher des centaines d'appels,
`install()` traduit ces littéraux au moment où chaque feuille de style est posée
(QWidget.setStyleSheet / QApplication.setStyleSheet) : un seul point, une seule
table, et le thème d'origine (« Nuit bleue ») n'est jamais touché.

Le thème se lit au démarrage (config `theme`, ou la variable PANDORA_THEME que
les harnais fixent) : en changer demande un redémarrage, comme avant.
"""
from __future__ import annotations

import os
import re

#: Thème d'ouverture (Matthieu 27/10/2026 : « garder les couleurs de PANDORA,
#: juste changer le bleuté par noir, c'est plus classe »).
DEFAULT = "noir"
#: Le thème d'origine, référence des littéraux à traduire (aucune traduction).
REFERENCE = "nuit"
#: Anciennes valeurs de la config (Sombre / Clair) : « Sombre » ouvre en Noir.
_LEGACY = {"dark": "noir", "light": "clair"}

#: Le thème d'origine : la référence des littéraux à traduire.
_NUIT = {
    "bg0": "#07080f", "bg1": "#0c0e1a", "bg2": "#111320", "bg3": "#181b2c", "bg4": "#1e2238",
    "sidebar": "#080910", "border": "#1a1e30", "border_bright": "#2a2f4a",
    "accent": "#4ecdc4", "accent_dim": "#2a7a75", "accent2": "#7c6bff", "accent2_dim": "#4a3fa0",
    "green": "#3ddc97", "red": "#ff4f6a", "orange": "#ff8c42",
    "text_primary": "#e6ecf5", "text_secondary": "#8a93ac", "text_dim": "#3d4460",
    "on_accent": "#ffffff",
}

def _bluish(r: int, g: int, b: int) -> bool:
    """Un bleu-gris de la famille « nuit » (fonds, bordures, gris bleutés) — pas
    un accent : les violets (r > g), turquoises et bleus vifs ne sont pas visés."""
    mx, mn = max(r, g, b), min(r, g, b)
    return b == mx and 4 <= b - mn <= 70 and r <= g + 10 and (r + g + b) / 3 < 190


def _gray(r: int, g: int, b: int) -> tuple:
    v = round((r + g + b) / 3)
    return v, v, v


def _neutral_hex(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    rgb = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    return "#%02x%02x%02x" % (_gray(*rgb) if _bluish(*rgb) else rgb)


THEMES: dict[str, dict] = {
    "noir": {
        "name": "Noir", "desc": "Les couleurs de PANDORA sur fond noir.",
        "cp": {k: (_neutral_hex(v) if k not in ("accent", "accent_dim", "accent2",
                                                 "accent2_dim", "green", "red", "orange",
                                                 "on_accent") else v)
               for k, v in _NUIT.items()},
        "accent_hover": "#6eded6", "accent2_hover": "#9d8fff", "nav_active": "#25d366",
        "badge": ("#1d1d1d", "#e8e8e8"), "neutral": True,
    },
    "nuit": {
        "name": "Nuit bleue", "desc": "Le bleu sombre d'origine, turquoise et violet.",
        "cp": dict(_NUIT),
        "accent_hover": "#6eded6", "accent2_hover": "#9d8fff", "nav_active": "#25d366",
        "badge": None,
    },
    "clair": {
        "name": "Clair", "desc": "Fond clair, pour les pièces lumineuses.",
        "cp": {
            "bg0": "#f0f2f9", "bg1": "#e8ebf4", "bg2": "#dde1ee", "bg3": "#d0d5e8",
            "bg4": "#c4cae0", "sidebar": "#e4e7f2", "border": "#b8c0d8",
            "border_bright": "#8e9abf", "accent": "#2fa89f", "accent_dim": "#1d7a73",
            "accent2": "#5e4edc", "accent2_dim": "#3d2fa0", "green": "#1a8a55",
            "red": "#cc2840", "orange": "#c06018", "text_primary": "#12152a",
            "text_secondary": "#3a4068", "text_dim": "#5e6898", "on_accent": "#ffffff",
        },
        "accent_hover": "#3cc0b6", "accent2_hover": "#7a6cf0", "nav_active": "#1a8a55",
        "badge": None, "ink": "#10131f",
    },
}
#: Trois apparences (Matthieu 27/10/2026 : « on enlève toutes les apparences
#: créées, elles sont vraiment moches ; on garde la nouvelle en noir, l'ancienne
#: en bleu et la claire »). Un thème retiré resté dans une config → « Noir ».
ORDER = ("noir", "nuit", "clair")
#: Les badges d'icônes (tuile bleu marine + dessin clair) que recolore
#: ui/icons.load_icon — PAS le logo d'AIODOS, qui garde ses couleurs.
BADGE_FILES = frozenset({
    "projets.png", "scenario.png", "storyboard.png", "mise_en_scene.png",
    "castings.png", "decors.png", "accesoires.png", "HMC.png", "vehicule.png",
    "camera.png", "vue_3d.png", "doublage.png", "draw_to_video.png",
    "seedance.png", "settings.png",
})


def normalize(key) -> str:
    k = str(key or "").strip().lower()
    k = _LEGACY.get(k, k)
    return k if k in THEMES else DEFAULT


def current_key() -> str:
    """Le thème de cette session : PANDORA_THEME (harnais), sinon la config."""
    env = os.environ.get("PANDORA_THEME")
    if env:
        return normalize(env)
    try:
        from core.config import load_config
        return normalize(load_config().get("theme"))
    except Exception:
        return DEFAULT


def theme(key: str | None = None) -> dict:
    return THEMES[normalize(key or current_key())]


def palette(key: str | None = None) -> dict:
    return dict(theme(key)["cp"])


def nav_active(key: str | None = None) -> str:
    return theme(key)["nav_active"]


def _rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    return f"{int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)}"


def literal_table(key: str | None = None) -> dict:
    """{littéral du thème d'origine (minuscules) : sa traduction} — vide pour
    « Nuit bleue ». Les rouges, verts et ors « sémantiques » (erreur, contact,
    soutien) restent ce qu'ils sont."""
    t = theme(key)
    if normalize(key or current_key()) == REFERENCE:
        return {}
    cp = t["cp"]
    table = {_NUIT[k].lower(): cp[k] for k in _NUIT if k not in ("on_accent", "green", "red",
                                                               "orange")}
    table["#0a0b16"] = cp["bg1"]
    table["#14162b"] = cp["bg2"]
    for lit in ("#6eded6", "#6fe0d8"):
        table[lit] = t["accent_hover"]
    for lit in ("#9d8fff", "#8d7dff", "#8f80ff", "#a090ff", "#9a8aff", "#7c6af7"):
        table[lit] = t["accent2_hover"]
    table["rgba(78,205,196,"] = f"rgba({_rgb(cp['accent'])},"
    table["rgba(124,107,255,"] = f"rgba({_rgb(cp['accent2'])},"
    table["rgba(124,106,247,"] = f"rgba({_rgb(cp['accent2'])},"
    table["rgba(122,90,248,"] = f"rgba({_rgb(cp['accent2'])},"
    table["rgba(7,8,15,"] = f"rgba({_rgb(cp['bg0'])},"
    return table


def ink(key: str | None = None) -> str:
    """Le texte sombre posé sur l'accent (« color: #07080f » dans le thème d'origine)."""
    t = theme(key)
    return t.get("ink") or t["cp"]["bg0"]


_translate = None
_HEX6 = re.compile(r"#[0-9a-fA-F]{6}(?![0-9a-fA-F])")
_RGB3 = re.compile(r"(rgba?\(\s*)(\d{1,3})(\s*,\s*)(\d{1,3})(\s*,\s*)(\d{1,3})")


def translate_css(css: str) -> str:
    """Traduit une feuille de style du thème d'origine vers le thème courant."""
    return _translate(css) if (_translate and css) else css


def translator(key: str | None = None):
    """La fonction qui traduit une feuille de style du thème d'origine vers le
    thème `key` (celui de la session par défaut) — None pour « Nuit bleue »."""
    table = literal_table(key)
    if not table:
        return None
    ink_color = ink(key)
    # « color: #07080f » = texte sombre sur un bouton d'accent : il suit l'encre
    # du thème, pas son fond (le Clair inverserait sinon le contraste).
    rx = re.compile(r"(?<![-\w])(color\s*:\s*)#07080f|"
                    + "|".join(re.escape(k) for k in sorted(table, key=len, reverse=True)),
                    re.IGNORECASE)

    def tr(css: str) -> str:
        return rx.sub(lambda m: (m.group(1) + ink_color) if m.group(1) is not None
                      else table[m.group(0).lower()], css)
    if not theme(key).get("neutral"):
        return tr

    # « Noir » : en plus de la table, TOUT bleu-gris écrit en dur (hexadécimal ou
    # rgb/rgba) devient le gris de même valeur ; les accents restent intacts.
    def _hex(m):
        return _neutral_hex(m.group(0))

    def _rgb3(m):
        r, g, b = (int(m.group(i)) for i in (2, 4, 6))
        if not _bluish(r, g, b):
            return m.group(0)
        v = _gray(r, g, b)[0]
        return f"{m.group(1)}{v}{m.group(3)}{v}{m.group(5)}{v}"

    def tr_neutral(css: str) -> str:
        out = _HEX6.sub(_hex, tr(css))
        return _RGB3.sub(_rgb3, out)
    return tr_neutral


def install() -> bool:
    """Branche la traduction sur setStyleSheet (une fois). Rend vrai si active."""
    global _translate
    if _translate is not None:
        return True
    tr = translator()
    if tr is None:
        return False
    _translate = tr
    from PyQt6.QtWidgets import QApplication, QWidget
    w_set, a_set = QWidget.setStyleSheet, QApplication.setStyleSheet

    def widget_set(self, css):
        return w_set(self, tr(css) if isinstance(css, str) and css else css)

    def app_set(self, css):
        return a_set(self, tr(css) if isinstance(css, str) and css else css)
    QWidget.setStyleSheet = widget_set
    QApplication.setStyleSheet = app_set
    return True


def recolor_badge(pix, key: str | None = None):
    """Un badge d'icône (fond bleu marine, dessin clair) aux couleurs du thème :
    le fond prend la teinte sombre du thème, le dessin sa couleur claire, en
    gardant l'anticrénelage (mélange selon la luminance). Inchangé si le thème
    garde les badges d'origine."""
    colors = theme(key)["badge"]
    if not colors or pix is None or pix.isNull():
        return pix
    from PyQt6.QtGui import QColor, QImage, QPixmap
    bg, fg = QColor(colors[0]), QColor(colors[1])
    img = pix.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    lo, hi = 0.20, 0.85             # bleu marine d'origine (≈ 0,15-0,21) → blanc du dessin
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            a = c.alpha()
            if a == 0:
                continue
            lum = (0.2126 * c.red() + 0.7152 * c.green() + 0.0722 * c.blue()) / 255
            t = max(0.0, min(1.0, (lum - lo) / (hi - lo)))
            img.setPixelColor(x, y, QColor(
                round(bg.red() + (fg.red() - bg.red()) * t),
                round(bg.green() + (fg.green() - bg.green()) * t),
                round(bg.blue() + (fg.blue() - bg.blue()) * t), a))
    out = QPixmap.fromImage(img)
    out.setDevicePixelRatio(pix.devicePixelRatio())
    return out


def nav_rgba(alpha: float, key: str | None = None) -> str:
    """La couleur de l'onglet actif en rgba() explicite (jamais de suffixe hex)."""
    return f"rgba({_rgb(nav_active(key))},{alpha:g})"
