"""
« Monter dans DaVinci Resolve » — menu Action du Storyboard (Cinéma uniquement).

Monte la DERNIÈRE prise de chaque plan, dans l'ordre du storyboard, sur une
nouvelle timeline de Resolve, par le pont (davinci/bridge_server.py v2) : clips
rangés dans PANDORA/SQnn, métadonnées scène / plan / prise / action, une couleur
par séquence. Sans pont (version gratuite ≥ 21.1, pont arrêté) : l'export de
timeline XML du même menu.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox

from core.i18n import translate

_TITLE = "Monter dans DaVinci Resolve"


def start(parent, shots: list[dict], project_name: str = "") -> None:
    from core.config import get_output_dir
    from core.timeline_clips import storyboard_clips
    clips = storyboard_clips(shots, get_output_dir())
    ready = [c for c in clips if c["path"]]
    without = len(clips) - len(ready)
    if not ready:
        QMessageBox.information(
            parent, translate(_TITLE),
            translate("Aucun plan de ce storyboard n'a encore de clip généré.") + "\n\n"
            + translate("Les clips sont cherchés dans le dossier vidéo du projet "
                        "(SQ3_P16_02.mp4…)."))
        return
    summary = translate("Plans montés (dernière prise) :") + f" {len(ready)}"
    if without:
        summary += "\n" + translate("Plans sans clip, ignorés :") + f" {without}"
    summary += "\n\n" + translate("Nom de la timeline dans DaVinci Resolve :")
    default = translate("Storyboard") + (f" — {project_name}" if project_name else "")
    name, ok = QInputDialog.getText(parent, translate(_TITLE), summary, text=default)
    name = (name or "").strip()
    if not ok or not name:
        return
    payload = [{"path": c["path"], "bin": c["bin"], "meta": c["meta"], "color": c["color"]}
               for c in ready]

    from davinci.bridge import resolve, translated
    from davinci.jobs import notify, run_job
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

    def _done(res):
        QApplication.restoreOverrideCursor()
        notify()
        if isinstance(res, tuple):
            ok_, result = res
        else:
            ok_, result = False, str((res or {}).get("error", ""))
        if not ok_:
            QMessageBox.warning(
                parent, translate(_TITLE),
                translated(str(result)) + "\n\n" + translate(
                    "Sans pont DaVinci : Action → « Exporter la timeline (XML) », puis "
                    "Fichier → Importer → Timeline dans Resolve."))
            return
        lines = [translate("Timeline créée dans DaVinci Resolve :")
                 + f" « {result.get('timeline', name)} »",
                 translate("Plans montés :") + f" {result.get('count', 0)}"]
        if result.get("reused"):
            lines.append(translate("Clips déjà présents, réutilisés :") + f" {result['reused']}")
        if without:
            lines.append(translate("Plans sans clip, ignorés :") + f" {without}")
        if result.get("missing"):
            lines.append(translate("Fichiers introuvables :") + f" {len(result['missing'])}")
        if result.get("errors"):
            lines.append(translate("Clips refusés par Resolve :") + f" {len(result['errors'])}")
            lines += ["  " + str(e) for e in result["errors"][:5]]
        QMessageBox.information(parent, translate(_TITLE), "\n".join(lines))

    run_job(resolve.build_timeline, _done, name, payload)
