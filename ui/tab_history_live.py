from PyQt6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
)
from PyQt6.QtCore import Qt
from ui.styles import C
from ui.widgets import section_label, HelpBlock
from core.history import load_history


class TabHistory(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.container = QWidget()
        self.setWidget(self.container)
        self.lay = QVBoxLayout(self.container)
        self.lay.setContentsMargins(20, 20, 20, 20)
        self.lay.setSpacing(10)
        self.lay.addWidget(HelpBlock("Historique des générations", [
            "▸ Retrouvez toutes les générations effectuées pour ce projet (50 entrées max).",
            "▸ Chaque entrée affiche le mode (T2V · I2V · Extension · Référence), le prompt, la durée et la résolution.",
            "▸ Les clips sont sauvegardés localement ; utilisez le bouton Import DaVinci au moment de la génération.",
        ], C))
        self.lay.addWidget(section_label("Générations récentes"))

        self.refresh()

    def refresh(self):
        while self.lay.count() > 2:
            item = self.lay.takeAt(2)
            if item.widget():
                item.widget().deleteLater()

        history = load_history()
        if not history:
            empty = QLabel("Aucune génération pour l'instant.\nLance une génération depuis T2V ou I2V !")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"color:{C['text_dim']};font-size:12px;padding:40px;")
            self.lay.addWidget(empty)
        else:
            for entry in history:
                self.lay.addWidget(self._make_item(entry))

        self.lay.addStretch()

    def add_entry(self, entry: dict):
        self.refresh()

    def _make_item(self, entry: dict) -> QFrame:
        status = entry.get("status", "done")
        mode   = entry.get("mode", "t2v").upper()
        prompt = entry.get("prompt", "")[:50]
        dur    = entry.get("duration", "?")
        res    = entry.get("resolution", "?")
        ts     = entry.get("generated_at", "")[:16].replace("T", " ")

        badge_map = {
            "done":  ("DONE", C["green"]),
            "error": ("ERR",  C["red"]),
            "gen":   ("GEN…", C["accent"]),
        }
        badge_txt, badge_col = badge_map.get(status, ("?", C["text_dim"]))

        icons = {"t2v": "🎬", "i2v": "🖼", "ref": "🎭", "ext": "➕"}
        icon  = icons.get(entry.get("mode", "t2v"), "🎬")

        item = QFrame()
        item.setStyleSheet(f"""
            QFrame{{background:{C['bg2']};border:1px solid {C['border']};border-radius:8px;}}
            QFrame:hover{{border-color:{C['border_bright']};background:{C['bg3']};}}
        """)
        item.setCursor(Qt.CursorShape.PointingHandCursor)

        row = QHBoxLayout(item)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(12)

        thumb = QLabel(icon)
        thumb.setFixedSize(52, 34)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet(
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 {C['accent_dim']},stop:1 #1a0e4a);border-radius:4px;font-size:18px;"
        )

        info = QVBoxLayout()
        info.setSpacing(3)
        t = QLabel(prompt or "(pas de prompt)")
        t.setStyleSheet(
            f"color:{C['text_primary']};font-size:11px;font-weight:700;"
            f"border:none;background:transparent;"
        )
        m = QLabel(f"{mode} · {dur}s · {res} · {ts}")
        m.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"border:none;background:transparent;"
        )
        info.addWidget(t)
        info.addWidget(m)

        badge = QLabel(badge_txt)
        badge.setFixedWidth(48)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"color:{badge_col};background:rgba(0,0,0,0.25);"
            f"border:1px solid {badge_col}44;border-radius:4px;"
            f"font-size:9px;font-weight:700;font-family:'Consolas',monospace;padding:3px 0;"
        )

        row.addWidget(thumb)
        row.addLayout(info, 1)
        row.addWidget(badge)
        return item
