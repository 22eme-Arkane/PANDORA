"""Rendu Qt hors écran du nouveau flux Scénario pour contrôle visuel manuel."""

from __future__ import annotations

import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication

from ui.page_scenario import PageScenario


def main(output_path: str) -> int:
    app = QApplication.instance() or QApplication([])
    # Le plugin Qt « offscreen » n'énumère aucune police système sur certaines
    # installations Windows : charger explicitement Segoe UI pour un rendu lisible.
    for font_path in (
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/consola.ttf",
    ):
        QFontDatabase.addApplicationFont(font_path)
    app.setFont(QFont("Segoe UI", 10))
    page = PageScenario()
    page.resize(1600, 900)
    page._stack.setCurrentIndex(1)
    page._current = {
        "id": "qa-pipeline",
        "formatted_content": (
            "INT. ATELIER — NUIT\n\n"
            "LENA traverse la pièce et ouvre la porte."
        ),
        "direction_note": "",
        "decoupage_content": "",
    }
    page._set_editor_text(page._current["formatted_content"])
    page._direction_note_edit.setPlainText(
        "## INTENTION GÉNÉRALE\n"
        "Une tension contenue qui s'accélère à l'ouverture de la porte.\n\n"
        "## STYLE VISUEL\n"
        "Contraste doux, palette cyan et ambre.\n\n"
        "## RYTHME ET MONTAGE\n"
        "Plans longs au départ, coupe franche sur l'ouverture."
    )
    page._apply_layout(
        "—— SÉQUENCE 1 — LA PORTE ——\n\n"
        "P01 | Plan moyen | Travelling avant | 3/4 | ~7s\n"
        "INT. ATELIER — NUIT\nLena traverse la pièce.\n"
        "→ SEEDANCE: Lena traverse lentement un atelier nocturne.\n\n"
        "P02 | Gros plan | Fixe | Face | ~4s\n"
        "Lena ouvre la porte.\n"
        "→ SEEDANCE: La main de Lena ouvre la porte dans une lumière ambre."
    )
    page._editor_tabs.setCurrentIndex(1)
    page._autosave_timer.stop()
    page.show()
    app.processEvents()
    ok = page.grab().save(output_path)
    page.close()
    app.processEvents()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
