"""
Studio Images — mini-application autonome de génération d'images.

Dialogue avec Claude (directeur artistique) + génération Nano Banana (fal.ai)
pour fabriquer bannières et vignettes YouTube.

Lancement :
    python studio_images/main.py
"""

import os
import sys

# Permet le lancement depuis n'importe quel dossier (imports à plat)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication

from styles import STYLESHEET
from window import StudioWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Studio Images")
    app.setStyleSheet(STYLESHEET)
    win = StudioWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
