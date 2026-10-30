# ── PANDORA Palette ──────────────────────────────────────────────────────────
# Les palettes vivent dans ui/themes (27/10/2026 : thèmes au choix dans les
# Paramètres — Nuit bleue d'origine, Noir & or, Néon, Émeraude, Braise, Clair).
from ui import themes as _themes

_CP_DARK = _themes.palette("nuit")
_CP_LIGHT = _themes.palette("clair")


def _load_theme_cp() -> dict:
    """La palette du thème de cette session (config `theme`, lue au démarrage)."""
    return _themes.palette()


CP = _load_theme_cp()

# ── Flèche des menus déroulants (2026-07-23) ─────────────────────────────────
# Le triangle en bordures CSS rendait un PETIT CARRÉ sur ce build Qt (retour
# Matthieu) → vraie image de chevron, utilisée par TOUS les QComboBox.
import os as _os
import sys as _sys
if getattr(_sys, "frozen", False):
    _ICONS_DIR = _os.path.join(_sys._MEIPASS, "assets", "icons")
else:
    _ICONS_DIR = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "assets", "icons")
COMBO_ARROW_URL = _os.path.join(_ICONS_DIR, "combo_arrow.png").replace("\\", "/")

# ── Seedance Palette (fond raccord PANDORA, accent purple) ────────────────────
C = {
    "bg0":           CP["bg0"],
    "bg1":           CP["bg1"],
    "bg2":           CP["bg2"],
    "bg3":           CP["bg3"],
    "border":        CP["border"],
    "border_bright": CP["border_bright"],
    "accent":        CP["accent2"],
    "accent_dim":    CP["accent2_dim"],
    "green":         CP["green"],
    "red":           CP["red"],
    "orange":        CP["orange"],
    "text_primary":  CP["text_primary"],
    "text_secondary":CP["text_secondary"],
    "text_dim":      CP["text_dim"],
}

# ── Seedance Stylesheet ───────────────────────────────────────────────────────
STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {C['bg0']};
    color: {C['text_primary']};
    font-family: 'Segoe UI', sans-serif;
}}
QTabWidget::pane {{ border: none; background: {C['bg0']}; }}
QTabBar {{ background: {C['bg1']}; }}
QTabBar::tab {{
    background: {C['bg1']}; color: {C['text_dim']};
    padding: 10px 16px; font-size: 11px; font-weight: 600;
    letter-spacing: 1px; border: none;
    border-bottom: 2px solid transparent; min-width: 60px;
}}
QTabBar::tab:hover {{ color: {C['text_secondary']}; background: {C['bg2']}; }}
QTabBar::tab:selected {{ color: {C['accent']}; border-bottom: 2px solid {C['accent']}; }}
QLabel {{ color: {C['text_primary']}; background: transparent; }}
QTextEdit {{
    background-color: {C['bg2']}; border: 1px solid {C['border']};
    border-radius: 8px; color: {C['text_primary']};
    font-size: 13px; padding: 10px;
}}
QTextEdit:focus {{ border: 1px solid {C['accent_dim']}; }}
QComboBox {{
    background-color: {C['bg2']}; border: 1px solid {C['border']};
    border-radius: 6px; color: {C['text_primary']};
    font-size: 12px; font-weight: 600; padding: 8px 12px; min-height: 18px;
}}
QComboBox:focus {{ border-color: {C['accent_dim']}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{
    image: url("{COMBO_ARROW_URL}"); width: 10px; height: 6px; margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {C['bg3']}; border: 1px solid {C['border_bright']};
    color: {C['text_primary']}; selection-background-color: {C['accent_dim']};
}}
QLineEdit {{
    background-color: {C['bg2']}; border: 1px solid {C['border']};
    border-radius: 6px; color: {C['text_primary']};
    font-size: 12px; font-family: 'Consolas', monospace; padding: 8px 12px;
}}
QLineEdit:focus {{ border-color: {C['accent_dim']}; }}
QPushButton {{
    background-color: {C['accent']}; color: white; border: none;
    border-radius: 8px; font-size: 12px; font-weight: 700;
    letter-spacing: 1px; padding: 13px 20px;
}}
QPushButton:hover {{ background-color: #8d7dff; }}
QPushButton:pressed {{ background-color: {C['accent_dim']}; }}
QPushButton:disabled {{ background-color: {C['bg3']}; color: {C['text_dim']}; }}
QProgressBar {{
    background-color: {C['bg3']}; border: none;
    border-radius: 3px; height: 6px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {C['accent_dim']}, stop:1 {C['accent']});
    border-radius: 3px;
}}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{
    background: {C['bg1']}; width: 6px; border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {C['border_bright']}; border-radius: 3px; min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
"""

# ── PANDORA Stylesheet ────────────────────────────────────────────────────────
PANDORA_STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {CP['bg1']};
    color: {CP['text_primary']};
    font-family: 'Segoe UI', sans-serif;
}}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{
    background: {CP['bg2']}; width: 6px; border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {CP['border_bright']}; border-radius: 3px; min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QLineEdit {{
    background-color: {CP['bg2']}; border: 1px solid {CP['border']};
    border-radius: 6px; color: {CP['text_primary']};
    font-size: 12px; padding: 8px 12px;
}}
QLineEdit:focus {{ border-color: {CP['accent_dim']}; }}
QPushButton {{
    background-color: {CP['accent']}; color: {CP['on_accent']};
    border: none; border-radius: 8px; font-size: 13px;
    font-weight: 700; padding: 13px 20px;
}}
QPushButton:hover {{ background-color: {CP['accent_dim']}; color: {CP['on_accent']}; }}
QPushButton:pressed {{ background-color: {CP['accent_dim']}; color: {CP['on_accent']}; }}
QPushButton:disabled {{ background-color: {CP['bg3']}; color: {CP['text_secondary']}; }}
QCheckBox {{
    color: {CP['text_primary']};
    font-size: 12px;
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 2px solid {CP['border_bright']};
    border-radius: 3px;
    background: {CP['bg3']};
}}
QCheckBox::indicator:checked {{
    background: {CP['accent']};
    border-color: {CP['accent']};
}}
QCheckBox::indicator:hover {{
    border-color: {CP['accent_dim']};
}}
QCheckBox::indicator:disabled {{
    background: {CP['bg2']};
    border-color: {CP['border']};
}}
QMessageBox {{ background: {CP['bg2']}; }}
QMessageBox QLabel {{ color: {CP['text_primary']}; }}
QInputDialog {{ background: {CP['bg2']}; }}
QInputDialog QLabel {{ color: {CP['text_primary']}; }}
QInputDialog QLineEdit {{
    background: {CP['bg3']}; border: 1px solid {CP['border_bright']};
    border-radius: 6px; color: {CP['text_primary']}; padding: 8px 12px;
}}
/* Dialogue de fichiers NON-NATIF (forcé pour éviter les crashs COM Windows) :
   neutralise le QPushButton global trop épais (padding 13px → boutons Open/Cancel
   tronqués) et donne un rendu propre aux champs/listes du dialogue. */
QFileDialog {{ background: {CP['bg2']}; }}
QFileDialog QLabel {{ color: {CP['text_primary']}; background: transparent; }}
QFileDialog QPushButton {{
    background-color: {CP['bg3']}; color: {CP['text_primary']};
    border: 1px solid {CP['border_bright']}; border-radius: 6px;
    font-size: 12px; font-weight: 600; padding: 6px 16px; min-width: 84px;
}}
QFileDialog QPushButton:hover {{ border-color: {CP['accent']}; }}
QFileDialog QPushButton:default {{
    background-color: {CP['accent']}; color: #07080f; border: none;
}}
QFileDialog QPushButton:default:hover {{ background-color: {CP['accent_dim']}; color: {CP['on_accent']}; }}
QFileDialog QComboBox {{
    background: {CP['bg3']}; border: 1px solid {CP['border']};
    border-radius: 6px; color: {CP['text_primary']}; padding: 4px 8px;
}}
QFileDialog QLineEdit {{
    background: {CP['bg3']}; border: 1px solid {CP['border']};
    border-radius: 6px; color: {CP['text_primary']}; padding: 6px 10px;
}}
QFileDialog QListView, QFileDialog QTreeView {{
    background: {CP['bg1']}; border: 1px solid {CP['border']}; color: {CP['text_primary']};
}}
QFileDialog QToolButton {{ background: transparent; border: none; padding: 4px; border-radius: 4px; }}
QFileDialog QToolButton:hover {{ background: {CP['bg3']}; }}
"""
