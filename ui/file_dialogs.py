"""Dialogues de fichiers Qt non-natifs AVEC vignettes d'images.

Deux objectifs réunis ici :

1. **Non-natif** (DontUseNativeDialog) — le dialogue NATIF Windows passe par le shell
   COM/OLE et plante sur certaines configs (vu dans %TEMP%\\pandora_fault.log :
   RPC_E_CANTCALLOUT_ININPUTSYNCCALL 0x8001010d / RPC_E_DISCONNECTED 0x80010108).

2. **Vignettes d'images** — l'explorateur Qt affiche par défaut une icône générique
   par type de fichier. Un `QFileIconProvider` génère ici un APERÇU (vignette) mis en
   cache pour chaque fichier image (png/jpg/webp/…), et on agrandit l'`iconSize` des
   vues internes (liste + détail) pour qu'elles soient lisibles. Bien plus pratique
   pour retrouver une image de référence.

On REMPLACE les 3 méthodes statiques de QFileDialog (getOpenFileName / getOpenFileNames
/ getSaveFileName) par des versions à base d'INSTANCE — seul moyen d'injecter un icon
provider. Le format de retour `(chemin, filtre)` / `([chemins], filtre)` est conservé à
l'identique → AUCUN appelant à modifier.
"""
import os

from PyQt6.QtWidgets import QFileDialog, QFileIconProvider, QListView, QTreeView
from PyQt6.QtCore import QFileInfo, QSize, Qt
from PyQt6.QtGui import QIcon, QPixmap

_IMG_EXT   = {"png", "jpg", "jpeg", "webp", "bmp", "gif"}
_THUMB     = QSize(72, 72)   # vignettes en mode liste/grille
_THUMB_ROW = QSize(40, 40)   # vignettes en mode détail (lignes)


class ThumbnailIconProvider(QFileIconProvider):
    """Renvoie une vignette pour les fichiers image, l'icône standard sinon.
    Les vignettes sont mises en cache (clé = chemin absolu) pour ne charger chaque
    image qu'une fois."""

    def __init__(self):
        super().__init__()
        self._cache: dict[str, QIcon] = {}

    def icon(self, info):
        # Surcharge QFileInfo → vignette ; l'autre surcharge (IconType) tombe au super.
        if isinstance(info, QFileInfo):
            try:
                if info.isFile() and info.suffix().lower() in _IMG_EXT:
                    path = info.absoluteFilePath()
                    ic = self._cache.get(path)
                    if ic is None:
                        pm = QPixmap(path)
                        if not pm.isNull():
                            ic = QIcon(pm.scaled(
                                _THUMB, Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation))
                            self._cache[path] = ic
                    if ic is not None:
                        return ic
            except Exception:
                pass
        return super().icon(info)


_provider: ThumbnailIconProvider | None = None


def _shared_provider() -> ThumbnailIconProvider:
    global _provider
    if _provider is None:
        _provider = ThumbnailIconProvider()
    return _provider


def _set_location(dlg: QFileDialog, directory: str):
    """Positionne le dossier ET, si `directory` est un chemin de FICHIER (suggestion
    de nom pour une sauvegarde), pré-sélectionne ce nom."""
    if not directory:
        return
    if os.path.isdir(directory):
        dlg.setDirectory(directory)
    else:
        parent = os.path.dirname(directory)
        if parent and os.path.isdir(parent):
            dlg.setDirectory(parent)
        dlg.selectFile(directory)


def apply_thumbnails(dlg: QFileDialog) -> QFileDialog:
    """Configure un QFileDialog : non-natif + vignettes d'images + iconSize agrandi
    sur les vues internes (liste + détail)."""
    dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dlg.setIconProvider(_shared_provider())
    for lv in dlg.findChildren(QListView):
        lv.setIconSize(_THUMB)
    for tv in dlg.findChildren(QTreeView):
        tv.setIconSize(_THUMB_ROW)
    return dlg


def install_thumbnail_file_dialogs():
    """Remplace les méthodes statiques de QFileDialog par des versions instance
    (non-natives + vignettes). À appeler UNE fois après la création du QApplication."""

    def getOpenFileName(parent=None, caption="", directory="", filter="",
                        initialFilter="", options=None):
        dlg = QFileDialog(parent, caption or "", "", filter or "")
        dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dlg.setFileMode(QFileDialog.FileMode.ExistingFile)
        _set_location(dlg, directory)
        if initialFilter:
            dlg.selectNameFilter(initialFilter)
        apply_thumbnails(dlg)
        if dlg.exec() == QFileDialog.DialogCode.Accepted:
            f = dlg.selectedFiles()
            return (f[0] if f else "", dlg.selectedNameFilter())
        return ("", "")

    def getOpenFileNames(parent=None, caption="", directory="", filter="",
                         initialFilter="", options=None):
        dlg = QFileDialog(parent, caption or "", "", filter or "")
        dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dlg.setFileMode(QFileDialog.FileMode.ExistingFiles)
        _set_location(dlg, directory)
        if initialFilter:
            dlg.selectNameFilter(initialFilter)
        apply_thumbnails(dlg)
        if dlg.exec() == QFileDialog.DialogCode.Accepted:
            return (dlg.selectedFiles(), dlg.selectedNameFilter())
        return ([], "")

    def getSaveFileName(parent=None, caption="", directory="", filter="",
                        initialFilter="", options=None):
        dlg = QFileDialog(parent, caption or "", "", filter or "")
        dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dlg.setFileMode(QFileDialog.FileMode.AnyFile)
        _set_location(dlg, directory)
        if initialFilter:
            dlg.selectNameFilter(initialFilter)
        apply_thumbnails(dlg)
        if dlg.exec() == QFileDialog.DialogCode.Accepted:
            f = dlg.selectedFiles()
            return (f[0] if f else "", dlg.selectedNameFilter())
        return ("", "")

    QFileDialog.getOpenFileName  = staticmethod(getOpenFileName)
    QFileDialog.getOpenFileNames = staticmethod(getOpenFileNames)
    QFileDialog.getSaveFileName  = staticmethod(getSaveFileName)
