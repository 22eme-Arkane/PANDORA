"""Splash de chargement PANDORA (2026-07-23, demande Matthieu).

Affiché pendant la CONSTRUCTION d'une fenêtre principale — ouverture d'une
édition depuis la page de démarrage, ou changement de projet (la fenêtre est
recréée par conception : chaque page relit le projet à sa construction, ce qui
garantit un état propre). La construction bloque le thread UI : les fenêtres
appellent ``pulse()`` entre leurs pages pour redonner la main à l'event loop —
la barre s'anime et l'utilisateur voit que rien n'a planté.
"""
from PyQt6.QtCore import Qt, QEventLoop
from PyQt6.QtWidgets import (QApplication, QLabel, QProgressBar, QVBoxLayout,
                             QWidget)

from ui.styles import CP

_ACTIVE: "LoadingSplash | None" = None


class LoadingSplash(QWidget):
    def __init__(self, text: str):
        super().__init__(None, Qt.WindowType.SplashScreen
                         | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(430, 250)

        card = QWidget(self)
        card.setObjectName("SplashCard")
        card.setGeometry(0, 0, 430, 250)
        card.setStyleSheet(
            f"QWidget#SplashCard{{background:{CP['bg1']};"
            f"border:1px solid {CP.get('accent2_dim', CP['border_bright'])};"
            f"border-radius:16px;}}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(32, 26, 32, 24)
        lay.setSpacing(10)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo = QLabel()
        logo.setFixedSize(64, 64)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("background:transparent;border:none;")
        try:
            from ui.icons import app_icon
            pix = app_icon().pixmap(64, 64)
            if not pix.isNull():
                logo.setPixmap(pix)
        except Exception:
            logo.setText("P")
        lay.addWidget(logo, 0, Qt.AlignmentFlag.AlignHCenter)

        title = QLabel("P A N D O R A")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:16px;font-weight:400;"
            "letter-spacing:5px;background:transparent;border:none;"
        )
        lay.addWidget(title)

        self._text = QLabel(text)
        self._text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text.setWordWrap(True)
        self._text.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;"
            "background:transparent;border:none;"
        )
        lay.addWidget(self._text)

        self._bar = QProgressBar()
        self._bar.setRange(0, 0)          # indéterminée : animation continue
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(5)
        self._bar.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border:none;border-radius:2px;}}"
            f"QProgressBar::chunk{{background:{CP['accent2']};border-radius:2px;}}"
        )
        lay.addWidget(self._bar)

        # Centré sur l'écran principal.
        try:
            geo = QApplication.primaryScreen().availableGeometry()
            self.move(geo.center().x() - self.width() // 2,
                      geo.center().y() - self.height() // 2)
        except Exception:
            pass

    def set_text(self, text: str):
        self._text.setText(text)


def open_splash(text: str) -> LoadingSplash:
    """Affiche le splash et le peint tout de suite (avant le gel de construction)."""
    global _ACTIVE
    close_splash()
    s = LoadingSplash(text)
    s.show()
    s.raise_()
    for _ in range(3):
        QApplication.processEvents()
    _ACTIVE = s
    return s


def pulse(text: str | None = None):
    """À appeler ENTRE les étapes de construction : repeint le splash et anime
    la barre (événements d'entrée exclus — aucune réentrance utilisateur)."""
    if _ACTIVE is None:
        return
    if text:
        _ACTIVE.set_text(text)
    QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)


def close_splash():
    global _ACTIVE
    if _ACTIVE is not None:
        try:
            _ACTIVE.close()
            _ACTIVE.deleteLater()
        except Exception:
            pass
        _ACTIVE = None
