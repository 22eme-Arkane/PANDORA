# ── PANDORA Palette ───────────────────────────────────────────────────────────
CP = {
    "bg0":           "#07080f",
    "bg1":           "#0c0e1a",
    "bg2":           "#111320",
    "bg3":           "#181b2c",
    "bg4":           "#1e2238",
    "sidebar":       "#080910",
    "border":        "#1a1e30",
    "border_bright": "#2a2f4a",
    "accent":        "#4ecdc4",    # Teal — PANDORA signature
    "accent_dim":    "#2a7a75",
    "accent2":       "#7c6bff",    # Purple — Seedance
    "accent2_dim":   "#4a3fa0",
    "green":         "#3ddc97",
    "red":           "#ff4f6a",
    "orange":        "#ff8c42",
    "text_primary":  "#e6ecf5",
    "text_secondary":"#8a93ac",
    "text_dim":      "#3d4460",
}

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
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid {C['text_dim']}; margin-right: 8px;
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
    background-color: {CP['accent']}; color: #ffffff;
    border: none; border-radius: 8px; font-size: 13px;
    font-weight: 700; padding: 13px 20px;
}}
QPushButton:hover {{ background-color: {CP['accent_dim']}; }}
QPushButton:disabled {{ background-color: {CP['bg3']}; color: {CP['text_dim']}; }}
QMessageBox {{ background: {CP['bg2']}; }}
QMessageBox QLabel {{ color: {CP['text_primary']}; }}
QInputDialog {{ background: {CP['bg2']}; }}
QInputDialog QLabel {{ color: {CP['text_primary']}; }}
QInputDialog QLineEdit {{
    background: {CP['bg3']}; border: 1px solid {CP['border_bright']};
    border-radius: 6px; color: {CP['text_primary']}; padding: 8px 12px;
}}
"""
