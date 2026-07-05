"""
Palette et feuille de style — reprise du look PANDORA (thème sombre),
copie minimale et autonome de ui/styles.py.
"""

# Palette sombre PANDORA
CP = {
    "bg0":           "#07080f",
    "bg1":           "#0c0e1a",
    "bg2":           "#111320",
    "bg3":           "#181b2c",
    "bg4":           "#1e2238",
    "border":        "#1a1e30",
    "border_bright": "#2a2f4a",
    "accent":        "#4ecdc4",   # Teal — signature PANDORA
    "accent_dim":    "#2a7a75",
    "accent2":       "#7c6bff",   # Violet
    "green":         "#3ddc97",
    "red":           "#ff4f6a",
    "orange":        "#ff8c42",
    "text_primary":  "#e6ecf5",
    "text_secondary":"#8a93ac",
    "text_dim":      "#3d4460",
}

# Bulles de chat
BUBBLE_USER = f"""
    background-color: {CP['bg4']};
    border: 1px solid {CP['border_bright']};
    border-radius: 10px; padding: 10px 12px;
    color: {CP['text_primary']}; font-size: 13px;
"""
BUBBLE_AI = f"""
    background-color: {CP['bg2']};
    border: 1px solid {CP['accent_dim']};
    border-radius: 10px; padding: 10px 12px;
    color: {CP['text_primary']}; font-size: 13px;
"""

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {CP['bg0']};
    color: {CP['text_primary']};
    font-family: 'Segoe UI', sans-serif;
}}
QLabel {{ color: {CP['text_primary']}; background: transparent; }}
QTextEdit {{
    background-color: {CP['bg2']}; border: 1px solid {CP['border']};
    border-radius: 8px; color: {CP['text_primary']};
    font-size: 13px; padding: 8px;
}}
QTextEdit:focus {{ border: 1px solid {CP['accent_dim']}; }}
QLineEdit {{
    background-color: {CP['bg2']}; border: 1px solid {CP['border']};
    border-radius: 6px; color: {CP['text_primary']};
    font-size: 12px; padding: 8px 12px;
}}
QLineEdit:focus {{ border-color: {CP['accent_dim']}; }}
QComboBox {{
    background-color: {CP['bg2']}; border: 1px solid {CP['border']};
    border-radius: 6px; color: {CP['text_primary']};
    font-size: 12px; font-weight: 600; padding: 7px 10px; min-height: 16px;
}}
QComboBox:focus {{ border-color: {CP['accent_dim']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid {CP['text_dim']}; margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {CP['bg3']}; border: 1px solid {CP['border_bright']};
    color: {CP['text_primary']}; selection-background-color: {CP['accent_dim']};
}}
QPushButton {{
    background-color: {CP['accent']}; color: #07080f; border: none;
    border-radius: 8px; font-size: 12px; font-weight: 700;
    letter-spacing: 0.5px; padding: 11px 16px;
}}
QPushButton:hover {{ background-color: #6fe0d8; }}
QPushButton:pressed {{ background-color: {CP['accent_dim']}; }}
QPushButton:disabled {{ background-color: {CP['bg3']}; color: {CP['text_dim']}; }}
QPushButton#secondary {{
    background-color: {CP['bg3']}; color: {CP['text_primary']};
    border: 1px solid {CP['border_bright']}; font-weight: 600;
}}
QPushButton#secondary:hover {{ background-color: {CP['bg4']}; }}
QProgressBar {{
    background-color: {CP['bg3']}; border: none; border-radius: 3px; height: 6px;
    text-align: center; color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {CP['accent_dim']}, stop:1 {CP['accent']});
    border-radius: 3px;
}}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: {CP['bg1']}; width: 7px; border-radius: 3px; }}
QScrollBar::handle:vertical {{
    background: {CP['border_bright']}; border-radius: 3px; min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar:horizontal {{ background: {CP['bg1']}; height: 7px; border-radius: 3px; }}
QScrollBar::handle:horizontal {{
    background: {CP['border_bright']}; border-radius: 3px; min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
QMessageBox, QInputDialog, QDialog {{ background: {CP['bg2']}; }}
QMessageBox QLabel, QInputDialog QLabel, QDialog QLabel {{ color: {CP['text_primary']}; }}
"""
