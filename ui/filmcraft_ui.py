"""ui/filmcraft_ui.py — FilmCraft dans l'interface (Cinéma ET Live, composant neutre).

- `send_clip(path, shot, on_done)` : l'import AUTOMATIQUE d'un clip généré dans le
  FilmCraft ouvert et relié (Studio IA des deux éditions), comme pour DaVinci.
- `montage(parent, shots, name)` : « Monter dans FilmCraft » du Storyboard.
- `FilmCraftPanel` : la section « FilmCraft » des Paramètres.

Le pont lui-même (CLI, jeton, chutiers) est core/filmcraft.py ; tout appel passe
par core.background.run_task : FilmCraft répond en quelques secondes, jamais sur
le fil de l'interface.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QCheckBox, QHBoxLayout, QInputDialog, QLabel,
                             QMessageBox, QPushButton, QVBoxLayout, QWidget)

from core.i18n import translate
from ui.styles import CP

_TITLE = "FilmCraft"


def explain(state: str) -> str:
    return {
        "not_installed": translate("FilmCraft n'est pas installé sur cet ordinateur."),
        "closed": translate("FilmCraft est fermé : « Ouvrir FilmCraft relié à PANDORA »."),
        "no_bridge": translate(
            "FilmCraft est ouvert sans le pont de PANDORA : fermez-le puis rouvrez-le depuis "
            "PANDORA, ou cochez « Toujours relier FilmCraft » dans les Paramètres."),
        "ready": translate("FilmCraft est ouvert et relié à PANDORA."),
    }.get(state, state)


# ── Import automatique d'un clip ──────────────────────────────────────────────

def send_clip(path: str, shot: dict | None = None, on_done=None):
    """Envoie le clip au FilmCraft relié, en arrière-plan, s'il est ouvert et que
    l'import automatique est coché. on_done(ok, texte) seulement si un envoi a eu
    lieu (FilmCraft fermé : silence, comme DaVinci déconnecté)."""
    from core import filmcraft
    if not path or not filmcraft.auto_import_enabled() or not filmcraft.is_installed():
        return None

    def work():
        if not filmcraft.port_open():
            return {"sent": False}
        from core.timeline_clips import import_meta
        sub_bin, _meta, _color = import_meta(shot, path)
        ok, err = filmcraft.import_clip(path, sub_bin)
        return {"sent": True, "ok": ok, "error": err, "bin": sub_bin}

    def done(res):
        if not isinstance(res, dict) or not res.get("sent") or on_done is None:
            return
        name = os.path.basename(path)
        if res.get("ok"):
            where = "PANDORA/" + res["bin"] if res.get("bin") else "PANDORA"
            on_done(True, f"✓ {name} → FilmCraft {where}")
        else:
            on_done(False, translate("Import FilmCraft impossible :") + " "
                    + str(res.get("error") or "")[:160])

    from core.background import run_task
    return run_task(work, done)


# ── « Monter dans FilmCraft » (Storyboard) ────────────────────────────────────

def _ask_open(parent, state: str) -> None:
    from core import filmcraft
    if state == "closed" and filmcraft.is_installed():
        r = QMessageBox.question(
            parent, translate(_TITLE),
            explain(state) + "\n\n" + translate("Ouvrir FilmCraft relié à PANDORA maintenant ?"))
        if r == QMessageBox.StandardButton.Yes:
            ok, err = filmcraft.launch()
            if ok:
                QMessageBox.information(parent, translate(_TITLE), translate(
                    "FilmCraft s'ouvre. Ouvrez ou créez votre projet, puis relancez la commande."))
            else:
                QMessageBox.warning(parent, translate(_TITLE), err)
        return
    QMessageBox.information(parent, translate(_TITLE), explain(state))


def montage(parent, shots: list, project_name: str = "") -> None:
    from core import filmcraft
    from core.config import get_output_dir
    from core.timeline_clips import storyboard_clips
    clips = storyboard_clips(shots, get_output_dir())
    ready = [c for c in clips if c["path"]]
    without = len(clips) - len(ready)
    if not ready:
        QMessageBox.information(parent, translate(_TITLE), translate(
            "Aucun plan de ce storyboard n'a encore de clip généré."))
        return
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        state = filmcraft.status()
    finally:
        QApplication.restoreOverrideCursor()
    if state != "ready":
        _ask_open(parent, state)
        return
    summary = translate("Plans montés (dernière prise) :") + f" {len(ready)}"
    if without:
        summary += "\n" + translate("Plans sans clip, ignorés :") + f" {without}"
    summary += "\n\n" + translate("Nom de la séquence dans FilmCraft :")
    default = translate("Storyboard") + (f" — {project_name}" if project_name else "")
    name, ok = QInputDialog.getText(parent, translate(_TITLE), summary, text=default)
    name = (name or "").strip()
    if not ok or not name:
        return
    payload = [{"path": c["path"], "bin": c["bin"]} for c in ready]
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

    def _done(res):
        QApplication.restoreOverrideCursor()
        if isinstance(res, tuple):
            ok_, result = res
        else:
            ok_, result = False, str((res or {}).get("error", ""))
        if not ok_:
            QMessageBox.warning(parent, translate(_TITLE),
                                translate("Montage dans FilmCraft impossible :") + "\n" + str(result))
            return
        lines = [translate("Séquence créée dans FilmCraft :") + f" « {name} »",
                 translate("Plans montés :") + f" {result.get('count', 0)}"]
        if result.get("reused"):
            lines.append(translate("Clips déjà présents, réutilisés :") + f" {result['reused']}")
        if without:
            lines.append(translate("Plans sans clip, ignorés :") + f" {without}")
        if result.get("errors"):
            lines.append(translate("Clips refusés par FilmCraft :") + f" {len(result['errors'])}")
        QMessageBox.information(parent, translate(_TITLE), "\n".join(lines))

    from core.background import run_task
    run_task(lambda: filmcraft.build_sequence(name, payload), _done)


# ── Section des Paramètres ────────────────────────────────────────────────────

class FilmCraftPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        from core import filmcraft
        import sys
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        intro = QLabel(translate(
            "FilmCraft, le logiciel de montage de la suite ArtCraft : PANDORA y envoie "
            "chaque clip généré (chutier PANDORA, un sous-chutier par séquence) et peut y "
            "monter le storyboard (Storyboard → Action → « Monter dans FilmCraft »)."))
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;background:transparent;")
        lay.addWidget(intro)

        row = QHBoxLayout()
        self.btn_open = QPushButton(translate("Ouvrir FilmCraft relié à PANDORA"))
        self.btn_open.setFixedHeight(34)
        self.btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent']};"
            f"border:1px solid {CP['accent']};border-radius:7px;font-size:12px;"
            f"font-weight:700;padding:0 16px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.12);}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};border-color:{CP['border']};}}")
        self.btn_open.clicked.connect(self._open)
        row.addWidget(self.btn_open)
        self.state = QLabel("")
        self.state.setWordWrap(True)
        self.state.setStyleSheet(f"color:{CP['text_dim']};font-size:11px;background:transparent;")
        row.addWidget(self.state, 1)
        lay.addLayout(row)

        self.auto = QCheckBox(translate("Envoyer chaque clip généré à FilmCraft quand il est ouvert"))
        self.auto.setChecked(filmcraft.auto_import_enabled())
        self.auto.toggled.connect(filmcraft.set_auto_import)
        lay.addWidget(self.auto)

        self.always = QCheckBox(translate(
            "Toujours relier FilmCraft à PANDORA, même ouvert depuis le menu Démarrer"))
        self.always.setToolTip(translate(
            "Enregistre le port et le jeton du pont dans les variables d'environnement de "
            "votre compte Windows. Prend effet au prochain lancement de FilmCraft."))
        self.always.setVisible(sys.platform.startswith("win"))
        try:
            self.always.setChecked(filmcraft.always_linked())
        except Exception:
            pass
        self.always.toggled.connect(self._always)
        lay.addWidget(self.always)

        installed = filmcraft.is_installed()
        self.btn_open.setEnabled(installed)
        self.auto.setEnabled(installed)
        self.always.setEnabled(installed)
        self.state.setText(explain("not_installed") if not installed else "")

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def refresh(self) -> None:
        from core import filmcraft
        from core.background import run_task
        if not filmcraft.is_installed():
            return

        def _done(state):
            try:
                self.state.setText(explain(str(state)))
                self.state.setStyleSheet(
                    f"color:{CP['green'] if state == 'ready' else CP['text_dim']};"
                    "font-size:11px;background:transparent;")
            except RuntimeError:
                pass
        run_task(filmcraft.status, _done)

    def _open(self) -> None:
        from core import filmcraft
        ok, err = filmcraft.launch()
        self.state.setText(translate("FilmCraft s'ouvre…") if ok else err)
        if ok:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(8000, self.refresh)

    def _always(self, enabled: bool) -> None:
        from core import filmcraft
        ok, err = filmcraft.set_always_linked(enabled)
        if not ok:
            self.always.blockSignals(True)
            self.always.setChecked(not enabled)
            self.always.blockSignals(False)
            QMessageBox.warning(self, translate(_TITLE), err)
