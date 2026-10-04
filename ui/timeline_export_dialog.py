"""
« Exporter la timeline (XML) » — menu Action du Storyboard (Cinéma ET Live).

Écrit une timeline Final Cut Pro 7 XML (core/timeline_export) : la dernière prise
de chaque plan, dans l'ordre du storyboard, bout à bout. DaVinci Resolve (gratuit
ou Studio) l'importe par Fichier → Importer → Timeline, Adobe Premiere par
Fichier → Importer. Aucun pont, aucun plugin : c'est la voie ouverte à tous,
y compris la version gratuite de Resolve ≥ 21.1 qui a perdu le scripting.
Module neutre : jamais d'import davinci.* ici (le Live l'utilise).
"""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from core.i18n import translate

_TITLE = "Exporter la timeline (XML)"


def _safe_name(text: str) -> str:
    keep = "".join(ch if (ch.isalnum() or ch in " -_—.") else " " for ch in text)
    return " ".join(keep.split()) or "PANDORA"


def _duration_label(frames: int, timebase: int, ntsc: bool) -> str:
    fps = timebase * (1000 / 1001 if ntsc else 1)
    seconds = int(round(frames / fps)) if fps else 0
    return f"{seconds // 60}:{seconds % 60:02d}"


def summary(rep: dict, without: int) -> str:
    """Bilan affiché après l'export (textes fixes traduits, chiffres ajoutés)."""
    fps = rep.get("timebase", 24) * (1000 / 1001 if rep.get("ntsc") else 1)
    lines = [
        translate("Timeline exportée :"), rep.get("path", ""), "",
        translate("Plans (dernière prise) :") + f" {rep.get('count', 0)}  ·  "
        + _duration_label(rep.get("frames", 0), rep.get("timebase", 24), rep.get("ntsc", False))
        + f"  ·  {rep.get('width', 0)}×{rep.get('height', 0)}  ·  {fps:g} "
        + translate("i/s"),
    ]
    if without:
        lines.append(translate("Plans sans clip, ignorés :") + f" {without}")
    if rep.get("skipped"):
        lines.append(translate("Clips illisibles, ignorés :") + f" {len(rep['skipped'])}")
    lines += ["",
              translate("DaVinci Resolve (gratuit ou Studio) : Fichier → Importer → Timeline, "
                        "puis choisissez ce fichier."),
              translate("Adobe Premiere : Fichier → Importer.")]
    warnings = []
    if rep.get("mixed_rate"):
        warnings.append(translate("Plans à une autre cadence que la timeline :")
                        + f" {len(rep['mixed_rate'])} — "
                        + translate("vérifiez « Mixed frame rate format » à l'import dans Resolve."))
    if rep.get("ten_bit"):
        warnings.append(translate("Clips en 10 bits :") + f" {len(rep['ten_bit'])} — "
                        + translate("la version gratuite de Resolve ne les lit pas."))
    if rep.get("non_ascii"):
        warnings.append(translate("Chemins avec accents :") + f" {len(rep['non_ascii'])} — "
                        + translate("si Resolve ne retrouve pas ces clips, indiquez-lui le "
                                    "dossier des vidéos quand il le demande."))
    if warnings:
        lines += [""] + ["⚠ " + w for w in warnings]
    return "\n".join(lines)


def export(parent, shots: list[dict], project_name: str = "") -> None:
    from core.config import get_output_dir
    from core.timeline_clips import storyboard_clips
    video_dir = get_output_dir()
    clips = storyboard_clips(shots, video_dir)
    ready = [c for c in clips if c["path"]]
    without = len(clips) - len(ready)
    if not ready:
        QMessageBox.information(
            parent, translate(_TITLE),
            translate("Aucun plan de ce storyboard n'a encore de clip généré.") + "\n\n"
            + translate("Les clips sont cherchés dans le dossier vidéo du projet "
                        "(SQ3_P16_02.mp4…)."))
        return
    name = translate("Storyboard") + (f" — {project_name}" if project_name else "")
    # À côté des clips par défaut : Blackmagic conseille de garder les médias d'une
    # timeline sous un même dossier pour faciliter le relink.
    default = os.path.join(video_dir, _safe_name(name) + ".xml")
    path, _sel = QFileDialog.getSaveFileName(
        parent, translate(_TITLE), default, translate("Timeline Final Cut Pro 7 XML (*.xml)"))
    if not path:
        return
    if not path.lower().endswith(".xml"):
        path += ".xml"

    from core.background import run_task
    from core.timeline_export import export_storyboard
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

    def _done(rep):
        QApplication.restoreOverrideCursor()
        if not isinstance(rep, dict) or not rep.get("ok"):
            detail = str((rep or {}).get("error") or "") if isinstance(rep, dict) else ""
            QMessageBox.warning(
                parent, translate(_TITLE),
                translate("Export impossible : aucun clip lisible (ffprobe).")
                + (f"\n\n{detail}" if detail else ""))
            return
        QMessageBox.information(parent, translate(_TITLE), summary(rep, without))

    run_task(export_storyboard, _done, path, name, ready)
