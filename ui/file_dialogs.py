"""Dialogues de fichiers Qt non-natifs — l'explorateur PANDORA.

Pourquoi non-natif ? Le dialogue NATIF Windows passe par le shell COM/OLE et plante
sur certaines configs (vu dans %TEMP%\\pandora_fault.log :
RPC_E_CANTCALLOUT_ININPUTSYNCCALL 0x8001010d / RPC_E_DISCONNECTED 0x80010108).
On force donc DontUseNativeDialog — et on rend l'explorateur Qt digne d'un vrai
explorateur :

1. **Vignettes d'images** — QFileIconProvider avec décodage À LA TAILLE de la
   vignette (QImageReader.setScaledSize : les JPEG sont décodés en DCT réduit →
   pas de gel UI sur un dossier de 200+ photos) + cache par chemin, invalidé si
   le fichier change (mtime).
2. **Barre latérale de raccourcis** — Bureau, Documents, Téléchargements, Images,
   Vidéos, Musique, lecteurs (C:\\ …), + dossier de sortie PANDORA et dossiers du
   projet courant quand ils existent.
3. **Mémoire par contexte** — dernier dossier visité mémorisé PAR TYPE de fichier
   (images / vidéos / audio / json / textes / autres) + taille de fenêtre + mode
   d'affichage, persistés dans data/file_dialog_prefs.json — JAMAIS dans
   data/config.json (qui contient les clés API).
4. **Barre d'adresse éditable** — le combo « Look in » devient éditable : chemin
   complet affiché, Entrée pour naviguer, complétion de chemins pendant la frappe.
   Le Ctrl+V « coller un chemin n'importe où » (retour bêta-test Pierre 2026-06-25)
   reste actif ailleurs dans le dialogue.
5. **Style PANDORA** — fond CP['bg1'], en-têtes de colonnes de la vue Détails
   lisibles (fond bg2), sélection accent en rgba() (jamais de suffixe hex-opacity),
   boutons Ouvrir/Enregistrer/Annuler contrastés (P4, retour Pierre), libellés FR
   quand l'interface est en français, tri par nom (dossiers d'abord sous Windows).

On REMPLACE les 3 méthodes statiques de QFileDialog (getOpenFileName / getOpenFileNames
/ getSaveFileName) par des versions à base d'INSTANCE — seul moyen d'injecter tout
cela. Le format de retour `(chemin, filtre)` / `([chemins], filtre)` est conservé à
l'identique → AUCUN appelant à modifier. (getExistingDirectory reste NATIF : aucun
crash COM observé sur le simple sélecteur de dossier, et le natif y est familier.)
"""
import json
import os
import re

from PyQt6.QtWidgets import (QFileDialog, QFileIconProvider, QListView, QTreeView,
                             QDialogButtonBox, QComboBox, QCompleter)
from PyQt6.QtCore import (QDir, QEvent, QFileInfo, QObject, QSize, QStandardPaths,
                          Qt, QTimer, QUrl)
from PyQt6.QtGui import (QFileSystemModel, QGuiApplication, QIcon, QImageReader,
                         QKeySequence, QPixmap)


# ── Préférences persistées (data/file_dialog_prefs.json) ─────────────────────
# Structure : {"last_dirs": {"images": "...", "videos": "..."},
#              "size": [1100, 700], "view_mode": 1}
# Fichier DÉDIÉ sous data/ — on n'écrit JAMAIS dans data/config.json (clés API).

_PREFS_FILENAME = "file_dialog_prefs.json"
_DEFAULT_W, _DEFAULT_H = 1100, 700


def _prefs_path() -> str:
    try:
        from core.paths import APP_ROOT
        root = APP_ROOT
    except Exception:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "data", _PREFS_FILENAME)


def _load_prefs() -> dict:
    try:
        with open(_prefs_path(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_prefs(update: dict) -> None:
    """Fusionne `update` dans les préférences existantes (écriture atomique)."""
    try:
        path = _prefs_path()
        prefs = _load_prefs()
        update = dict(update)
        last_dirs = update.pop("last_dirs", None)
        if isinstance(last_dirs, dict):
            merged = prefs.get("last_dirs")
            if not isinstance(merged, dict):
                merged = {}
            merged.update(last_dirs)
            prefs["last_dirs"] = merged
        prefs.update(update)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(prefs, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass


# ── Contexte (type de fichiers) déduit du filtre de l'appelant ────────────────
# La PREMIÈRE extension du filtre décide : « Vidéos (*.mp4 … *.gif) » → videos,
# « Images (*.png … *.gif) » → images. Le .gif ambigu est donc résolu par l'ordre.

_EXT_TO_CTX = {}
for _ctx, _exts in (
    ("images", ("png", "jpg", "jpeg", "webp", "bmp", "gif", "tif", "tiff")),
    ("videos", ("mp4", "mov", "webm", "m4v", "avi", "mkv", "mpg", "mpeg")),
    ("audio",  ("mp3", "wav", "m4a", "aac", "ogg", "flac", "aif", "aiff")),
    ("json",   ("json",)),
    ("textes", ("txt", "docx", "pdf", "doc", "rtf", "md")),
):
    for _e in _exts:
        _EXT_TO_CTX.setdefault(_e, _ctx)


def _context_for_filter(name_filter: str) -> str:
    for ext in re.findall(r"\*\.([A-Za-z0-9]+)", name_filter or ""):
        ctx = _EXT_TO_CTX.get(ext.lower())
        if ctx:
            return ctx
    return "autres"


def _remember_dir(context: str, path: str) -> None:
    """Mémorise le dossier du fichier choisi comme dernier dossier du contexte."""
    if not path:
        return
    d = path if os.path.isdir(path) else os.path.dirname(path)
    if d and os.path.isdir(d):
        _save_prefs({"last_dirs": {context: d}})


def _remember_geometry(dlg: QFileDialog) -> None:
    """Mémorise la taille du dialogue et le mode d'affichage (liste/détails)."""
    try:
        _save_prefs({"size": [dlg.width(), dlg.height()],
                     "view_mode": int(dlg.viewMode().value)})
    except Exception:
        pass


# ── Barre latérale de raccourcis ──────────────────────────────────────────────

def _sidebar_urls() -> list:
    """Raccourcis du vrai explorateur : dossiers PANDORA/projet, dossiers
    utilisateur standards, puis les lecteurs. Doublons et dossiers absents filtrés."""
    urls, seen = [], set()

    def add(p):
        try:
            if p and os.path.isdir(p):
                key = os.path.normcase(os.path.normpath(p))
                if key not in seen:
                    seen.add(key)
                    urls.append(QUrl.fromLocalFile(p))
        except Exception:
            pass

    # Dossiers PANDORA (projet courant + dossier de sortie) — les plus utilisés.
    try:
        from core.context import get_project_path, get_data_root
        pp = get_project_path()
        if pp:
            add(pp)               # racine du projet (nom lisible dans la barre)
            add(get_data_root())  # <projet>/data
    except Exception:
        pass
    try:
        from core.config import get_output_dir
        add(get_output_dir())
    except Exception:
        pass

    # Dossiers utilisateur standards.
    loc = QStandardPaths.StandardLocation
    for what in (loc.DesktopLocation, loc.DocumentsLocation, loc.DownloadLocation,
                 loc.PicturesLocation, loc.MoviesLocation, loc.MusicLocation):
        try:
            add(QStandardPaths.writableLocation(what))
        except Exception:
            pass

    # Lecteurs (C:\, D:\ …).
    try:
        for fi in QDir.drives():
            add(fi.absoluteFilePath())
    except Exception:
        pass
    return urls


# ── Coller un chemin (Ctrl+V) n'importe où dans le dialogue ───────────────────

class _PathPasteFilter(QObject):
    """Coller un chemin (Ctrl+V) n'importe où dans le dialogue pour y naviguer.

    Complète la barre d'adresse éditable : le Ctrl+V non consommé par un champ
    (liste, vue, dialogue) navigue si le presse-papier contient un CHEMIN. Les
    champs texte (adresse, nom de fichier) gardent leur collage normal.
    Retour bêta-test Pierre (2026-06-25)."""

    def __init__(self, dlg: QFileDialog):
        super().__init__(dlg)
        self._dlg = dlg

    def eventFilter(self, obj, ev):
        if (ev.type() == QEvent.Type.KeyPress
                and ev.matches(QKeySequence.StandardKey.Paste)):
            text = (QGuiApplication.clipboard().text() or "").strip().strip('"')
            if text:
                if os.path.isdir(text):
                    self._dlg.setDirectory(text)
                    return True
                if os.path.isfile(text):
                    parent = os.path.dirname(text)
                    if parent:
                        self._dlg.setDirectory(parent)
                    self._dlg.selectFile(text)
                    return True
        return False


# ── Vignettes d'images ────────────────────────────────────────────────────────

_IMG_EXT   = {"png", "jpg", "jpeg", "webp", "bmp", "gif"}
_THUMB     = QSize(96, 96)   # vignettes en mode liste/grille (un cran plus grand)
_THUMB_ROW = QSize(48, 48)   # vignettes en mode détail (lignes)
_MAX_THUMB_BYTES = 48 * 1024 * 1024   # au-delà : icône générique (pas de décodage)
_MAX_CACHE = 4000                     # garde-fou mémoire (≈ quelques Mo d'icônes)


class ThumbnailIconProvider(QFileIconProvider):
    """Renvoie une vignette pour les fichiers image, l'icône standard sinon.

    Le décodage se fait DIRECTEMENT à la taille de la vignette via
    QImageReader.setScaledSize (JPEG : décodage DCT réduit — bien plus rapide
    qu'un QPixmap plein format redimensionné ensuite). Les vignettes sont mises
    en cache (clé = chemin absolu) et invalidées si le fichier change (mtime).
    Le modèle de fichiers ne demande les icônes que des lignes VISIBLES → le
    remplissage reste paresseux, pas de gel UI sur un gros dossier."""

    def __init__(self):
        super().__init__()
        self._cache: dict[str, QIcon] = {}
        self._mtimes: dict[str, float] = {}

    def icon(self, info):
        # Surcharge QFileInfo → vignette ; l'autre surcharge (IconType) tombe au super.
        if isinstance(info, QFileInfo):
            try:
                if info.isFile() and info.suffix().lower() in _IMG_EXT:
                    if info.size() > _MAX_THUMB_BYTES:
                        return super().icon(info)
                    path = info.absoluteFilePath()
                    try:
                        mtime = float(info.lastModified().toSecsSinceEpoch())
                    except Exception:
                        mtime = 0.0
                    ic = self._cache.get(path)
                    if ic is not None and self._mtimes.get(path) == mtime:
                        return ic
                    ic = self._make_thumb(path)
                    if ic is not None:
                        if len(self._cache) >= _MAX_CACHE:
                            self._cache.clear()
                            self._mtimes.clear()
                        self._cache[path] = ic
                        self._mtimes[path] = mtime
                        return ic
            except Exception:
                pass
        return super().icon(info)

    @staticmethod
    def _make_thumb(path: str) -> QIcon | None:
        reader = QImageReader(path)
        reader.setAutoTransform(True)   # respecte l'orientation EXIF
        src = reader.size()             # lu dans l'en-tête, sans décoder l'image
        if src.isValid() and (src.width() > _THUMB.width()
                              or src.height() > _THUMB.height()):
            reader.setScaledSize(src.scaled(
                _THUMB, Qt.AspectRatioMode.KeepAspectRatio))
        img = reader.read()
        if img.isNull():
            return None
        return QIcon(QPixmap.fromImage(img))


_provider: ThumbnailIconProvider | None = None


def _shared_provider() -> ThumbnailIconProvider:
    global _provider
    if _provider is None:
        _provider = ThumbnailIconProvider()
    return _provider


# ── Positionnement initial ────────────────────────────────────────────────────

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


def _initial_location(dlg: QFileDialog, context: str, directory: str):
    """Le dossier demandé par l'APPELANT prime ; sinon on rouvre le DERNIER dossier
    visité pour ce contexte (images / vidéos / audio / json / textes)."""
    last_dirs = _load_prefs().get("last_dirs")
    remembered = last_dirs.get(context, "") if isinstance(last_dirs, dict) else ""
    if directory:
        # Suggestion de nom sans dossier valide → on la pose dans le dossier mémorisé.
        parent = os.path.dirname(directory)
        if (not os.path.isdir(directory)
                and not (parent and os.path.isdir(parent))
                and remembered and os.path.isdir(remembered)):
            dlg.setDirectory(remembered)
        _set_location(dlg, directory)
        return
    if remembered and os.path.isdir(remembered):
        dlg.setDirectory(remembered)


# ── Géométrie (taille mémorisée, bornée à l'écran) ────────────────────────────

def _apply_geometry(dlg: QFileDialog):
    prefs = _load_prefs()
    w, h = _DEFAULT_W, _DEFAULT_H
    size = prefs.get("size")
    if isinstance(size, (list, tuple)) and len(size) == 2:
        try:
            w, h = int(size[0]), int(size[1])
        except Exception:
            w, h = _DEFAULT_W, _DEFAULT_H
    try:
        scr = dlg.screen() or QGuiApplication.primaryScreen()
        if scr is not None:
            avail = scr.availableGeometry()
            w = min(w, max(avail.width() - 40, 400))
            h = min(h, max(avail.height() - 40, 300))
    except Exception:
        pass
    dlg.resize(max(w, 760), max(h, 480))
    try:
        vm = prefs.get("view_mode")
        if vm is not None:
            dlg.setViewMode(QFileDialog.ViewMode(int(vm)))
    except Exception:
        pass


# ── Style PANDORA ─────────────────────────────────────────────────────────────

def _rgba(hex_color: str, pct: int) -> str:
    """'#4ecdc4', 18 → 'rgba(78,205,196,18%)' — JAMAIS de suffixe hex-opacity."""
    try:
        c = hex_color.lstrip("#")
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        return f"rgba({r},{g},{b},{pct}%)"
    except Exception:
        return "transparent"


def _dialog_stylesheet() -> str:
    try:
        from ui.styles import CP
    except Exception:
        return ""
    sel = _rgba(CP["accent"], 22)
    hov = _rgba(CP["accent"], 10)
    return f"""
QFileDialog {{ background: {CP['bg1']}; }}
QFileDialog QLabel {{ color: {CP['text_secondary']}; font-size: 12px; }}

/* Barre d'adresse (combo « Emplacement » rendu éditable) */
QFileDialog QComboBox#lookInCombo {{
    background: {CP['bg2']}; color: {CP['text_primary']};
    border: 1px solid {CP['border']}; border-radius: 6px;
    min-height: 30px; padding: 2px 10px; font-size: 12px;
}}
QFileDialog QComboBox#lookInCombo:focus {{ border-color: {CP['accent_dim']}; }}
QFileDialog QComboBox#lookInCombo QLineEdit {{
    background: transparent; border: none;
    color: {CP['text_primary']}; font-size: 12px;
}}

/* Champ « Nom du fichier » + combo de filtre */
QFileDialog QLineEdit#fileNameEdit {{
    background: {CP['bg2']}; color: {CP['text_primary']};
    border: 1px solid {CP['border']}; border-radius: 6px;
    min-height: 28px; padding: 2px 10px; font-size: 12px;
}}
QFileDialog QLineEdit#fileNameEdit:focus {{ border-color: {CP['accent_dim']}; }}
QFileDialog QComboBox#fileTypeCombo {{
    background: {CP['bg2']}; color: {CP['text_primary']};
    border: 1px solid {CP['border']}; border-radius: 6px;
    min-height: 28px; padding: 2px 10px; font-size: 12px;
}}

/* Boutons outils (précédent / parent / nouveau dossier / mode liste-détails) */
QFileDialog QToolButton {{
    background: transparent; border: 1px solid transparent;
    border-radius: 6px; padding: 4px;
}}
QFileDialog QToolButton:hover {{ background: {CP['bg3']}; border-color: {CP['border']}; }}
QFileDialog QToolButton:pressed {{ background: {CP['bg3']}; }}
QFileDialog QToolButton:checked {{ background: {CP['bg3']}; border-color: {CP['accent_dim']}; }}

/* En-têtes de colonnes de la vue Détails (fond du QHeaderView AUSSI : sans lui,
   la zone vide à droite de la dernière colonne resterait blanche) */
QFileDialog QHeaderView {{ background: {CP['bg2']}; border: none; }}
QFileDialog QHeaderView::section {{
    background: {CP['bg2']}; color: {CP['text_secondary']};
    border: none; border-right: 1px solid {CP['border']};
    border-bottom: 1px solid {CP['border']};
    padding: 5px 10px; font-size: 11px; font-weight: 600;
}}
QFileDialog QHeaderView::section:hover {{ background: {CP['bg3']}; color: {CP['text_primary']}; }}

/* Vues fichiers (liste + détails) */
QFileDialog QTreeView, QFileDialog QListView {{
    background: {CP['bg1']}; color: {CP['text_primary']};
    border: 1px solid {CP['border']}; border-radius: 6px;
    outline: none; font-size: 12px;
}}
QFileDialog QTreeView::item {{ padding: 2px 4px; }}
QFileDialog QListView::item {{ padding: 2px 4px; border-radius: 4px; }}
QFileDialog QTreeView::item:hover, QFileDialog QListView::item:hover {{
    background: {hov};
}}
QFileDialog QTreeView::item:selected, QFileDialog QListView::item:selected {{
    background: {sel}; color: {CP['text_primary']};
}}

/* Barre latérale de raccourcis */
QFileDialog QListView#sidebar {{
    background: {CP['bg0']}; color: {CP['text_secondary']};
    border: 1px solid {CP['border']}; border-radius: 6px;
    padding: 4px; font-size: 12px;
}}
QFileDialog QListView#sidebar::item {{ padding: 6px; border-radius: 6px; }}
QFileDialog QListView#sidebar::item:hover {{ background: {hov}; color: {CP['text_primary']}; }}
QFileDialog QListView#sidebar::item:selected {{ background: {sel}; color: {CP['accent']}; }}

QFileDialog QSplitter::handle {{ background: transparent; }}

/* Scrollbars fines et sombres (les scrollbars par défaut ressortent claires) */
QFileDialog QScrollBar:vertical {{
    background: {CP['bg1']}; width: 10px; margin: 0; border: none; border-radius: 5px;
}}
QFileDialog QScrollBar:horizontal {{
    background: {CP['bg1']}; height: 10px; margin: 0; border: none; border-radius: 5px;
}}
QFileDialog QScrollBar::handle:vertical {{
    background: {CP['bg3']}; border-radius: 5px; min-height: 24px;
}}
QFileDialog QScrollBar::handle:horizontal {{
    background: {CP['bg3']}; border-radius: 5px; min-width: 24px;
}}
QFileDialog QScrollBar::handle:hover {{ background: {CP['accent_dim']}; }}
QFileDialog QScrollBar::add-line, QFileDialog QScrollBar::sub-line {{
    width: 0; height: 0; border: none; background: transparent;
}}
QFileDialog QScrollBar::add-page, QFileDialog QScrollBar::sub-page {{
    background: transparent;
}}
QFileDialog QAbstractScrollArea::corner {{ background: {CP['bg1']}; border: none; }}
"""


def _style_dialog_buttons(dlg: QFileDialog):
    """Rend les boutons Ouvrir / Enregistrer / Annuler LISIBLES sur fond sombre.
    Le dialogue non-natif hérite d'un style peu contrasté → retour bêta-test
    Pierre : le bouton « Ouvrir » (au-dessus d'« Annuler ») paraissait invisible.
    Le bouton d'acceptation passe en accent plein ; les autres en contour lisible."""
    try:
        from ui.styles import CP
    except Exception:
        return
    accept_ss = (
        f"QPushButton{{background:{CP['accent']};color:#07080f;border:none;"
        f"border-radius:7px;font-size:12px;font-weight:700;padding:6px 20px;min-width:96px;}}"
        f"QPushButton:hover{{background:{CP.get('accent_dim', CP['accent'])};color:#fff;}}"
        f"QPushButton:disabled{{background:{CP['bg3']};color:{CP.get('text_dim', '#6f7290')};}}"
    )
    other_ss = (
        f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
        f"border:1px solid {CP['border']};border-radius:7px;font-size:12px;"
        f"font-weight:600;padding:6px 18px;min-width:88px;}}"
        f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
    )
    for bb in dlg.findChildren(QDialogButtonBox):
        for b in bb.buttons():
            if bb.buttonRole(b) == QDialogButtonBox.ButtonRole.AcceptRole:
                b.setStyleSheet(accept_ss)   # Ouvrir / Enregistrer
            else:
                b.setStyleSheet(other_ss)     # Annuler (et autres)


# ── Libellés FR (le dialogue Qt est anglophone par défaut) ────────────────────
# Bilingue GÉRÉ ICI via core.i18n.get_lang() (dialogue recréé à chaque appel) —
# ces chaînes ne passent PAS par _FR_TO_EN (système bilingue dédié, cf. manuel).

def _apply_labels(dlg: QFileDialog):
    try:
        from core.i18n import get_lang
        lang = get_lang() or "fr"
    except Exception:
        lang = "fr"
    if lang != "fr":
        return   # interface EN → libellés Qt d'origine (Open / Cancel / File name…)
    try:
        lab = QFileDialog.DialogLabel
        save = dlg.acceptMode() == QFileDialog.AcceptMode.AcceptSave
        dlg.setLabelText(lab.LookIn, "Emplacement :")
        dlg.setLabelText(lab.FileName, "Nom du fichier :")
        dlg.setLabelText(lab.FileType, "Type :")
        dlg.setLabelText(lab.Accept, "Enregistrer" if save else "Ouvrir")
        dlg.setLabelText(lab.Reject, "Annuler")
    except Exception:
        pass


# ── Barre d'adresse éditable ──────────────────────────────────────────────────

def _make_path_bar_editable(dlg: QFileDialog):
    """Le combo « Look in » du non-natif est austère et non éditable → on le rend
    ÉDITABLE : chemin complet affiché, Entrée pour naviguer, complétion de chemins.
    Le texte est resynchronisé après chaque navigation (vues, barre latérale,
    boutons précédent/parent — tout passe par le combo interne du QFileDialog)."""
    combo = dlg.findChild(QComboBox, "lookInCombo")
    if combo is None:
        return
    try:
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        le = combo.lineEdit()
        if le is None:
            return
        le.setClearButtonEnabled(True)

        def _sync(*_a):
            try:
                le.setText(os.path.normpath(dlg.directory().absolutePath()))
            except Exception:
                pass

        def _navigate():
            t = os.path.expandvars(os.path.expanduser(
                (le.text() or "").strip().strip('"')))
            if os.path.isdir(t):
                dlg.setDirectory(t)
            elif os.path.isfile(t):
                parent = os.path.dirname(t)
                if parent:
                    dlg.setDirectory(parent)
                dlg.selectFile(t)
            _sync()

        le.returnPressed.connect(_navigate)
        dlg.directoryEntered.connect(_sync)
        # Toute navigation (vues, barre latérale, historique) met à jour le combo →
        # on resynchronise le texte APRÈS le traitement interne du QFileDialog.
        combo.currentIndexChanged.connect(lambda *_: QTimer.singleShot(0, _sync))

        # Complétion de chemins pendant la frappe (dossiers + lecteurs).
        try:
            fsm = QFileSystemModel(le)
            fsm.setRootPath("")
            fsm.setFilter(QDir.Filter.AllDirs | QDir.Filter.Drives
                          | QDir.Filter.NoDotAndDotDot)
            comp = QCompleter(fsm, le)
            comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            le.setCompleter(comp)
        except Exception:
            pass
        _sync()
    except Exception:
        pass


# ── Configuration complète d'un dialogue ──────────────────────────────────────

def apply_thumbnails(dlg: QFileDialog) -> QFileDialog:
    """Configure un QFileDialog : non-natif + vignettes d'images + barre latérale
    de raccourcis + barre d'adresse éditable + taille/mode mémorisés + style
    PANDORA. (Nom historique — c'est le point d'entrée unique du module.)"""
    dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dlg.setIconProvider(_shared_provider())
    for lv in dlg.findChildren(QListView):
        if lv.objectName() == "sidebar":
            lv.setIconSize(QSize(16, 16))   # la barre latérale garde des icônes fines
        else:
            lv.setIconSize(_THUMB)
            lv.setSpacing(2)                # espacement propre entre vignettes
    for tv in dlg.findChildren(QTreeView):
        tv.setIconSize(_THUMB_ROW)
        try:   # tri par nom par défaut (dossiers d'abord sous Windows)
            tv.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        except Exception:
            pass
    try:
        dlg.setSidebarUrls(_sidebar_urls())
    except Exception:
        pass
    _apply_geometry(dlg)         # ~1100×700, mémorisée si l'utilisateur la change
    _style_dialog_buttons(dlg)   # P4 — boutons Ouvrir/Annuler lisibles (fond sombre)
    _apply_labels(dlg)
    try:
        dlg.setStyleSheet(_dialog_stylesheet())
    except Exception:
        pass
    _make_path_bar_editable(dlg)
    # Coller un chemin (Ctrl+V) pour naviguer — retour Pierre.
    dlg.installEventFilter(_PathPasteFilter(dlg))
    dlg.finished.connect(lambda _r, d=dlg: _remember_geometry(d))
    return dlg


def _create_dialog(parent, caption, directory, name_filter, initial_filter,
                   accept_mode, file_mode):
    """Fabrique commune des 3 statics : dialogue configuré + contexte mémoire."""
    dlg = QFileDialog(parent, caption or "", "", name_filter or "")
    dlg.setAcceptMode(accept_mode)
    dlg.setFileMode(file_mode)
    ctx = _context_for_filter(name_filter or "")
    _initial_location(dlg, ctx, directory or "")
    if initial_filter:
        dlg.selectNameFilter(initial_filter)
    apply_thumbnails(dlg)
    return dlg, ctx


def install_thumbnail_file_dialogs():
    """Remplace les méthodes statiques de QFileDialog par des versions instance
    (non-natives + explorateur PANDORA complet). À appeler UNE fois après la
    création du QApplication. Formats de retour inchangés."""

    # NB : deleteLater() après lecture du résultat — un dialogue créé avec un
    # parent survivrait sinon jusqu'à la mort du parent (et porte désormais un
    # QFileSystemModel de complétion). Qt déconseille WA_DeleteOnClose + exec().

    def getOpenFileName(parent=None, caption="", directory="", filter="",
                        initialFilter="", options=None):
        dlg, ctx = _create_dialog(parent, caption, directory, filter, initialFilter,
                                  QFileDialog.AcceptMode.AcceptOpen,
                                  QFileDialog.FileMode.ExistingFile)
        try:
            if dlg.exec() == QFileDialog.DialogCode.Accepted:
                f = dlg.selectedFiles()
                if f:
                    _remember_dir(ctx, f[0])
                return (f[0] if f else "", dlg.selectedNameFilter())
            return ("", "")
        finally:
            dlg.deleteLater()

    def getOpenFileNames(parent=None, caption="", directory="", filter="",
                         initialFilter="", options=None):
        dlg, ctx = _create_dialog(parent, caption, directory, filter, initialFilter,
                                  QFileDialog.AcceptMode.AcceptOpen,
                                  QFileDialog.FileMode.ExistingFiles)
        try:
            if dlg.exec() == QFileDialog.DialogCode.Accepted:
                f = dlg.selectedFiles()
                if f:
                    _remember_dir(ctx, f[0])
                return (f, dlg.selectedNameFilter())
            return ([], "")
        finally:
            dlg.deleteLater()

    def getSaveFileName(parent=None, caption="", directory="", filter="",
                        initialFilter="", options=None):
        dlg, ctx = _create_dialog(parent, caption, directory, filter, initialFilter,
                                  QFileDialog.AcceptMode.AcceptSave,
                                  QFileDialog.FileMode.AnyFile)
        try:
            if dlg.exec() == QFileDialog.DialogCode.Accepted:
                f = dlg.selectedFiles()
                if f:
                    _remember_dir(ctx, f[0])
                return (f[0] if f else "", dlg.selectedNameFilter())
            return ("", "")
        finally:
            dlg.deleteLater()

    QFileDialog.getOpenFileName  = staticmethod(getOpenFileName)
    QFileDialog.getOpenFileNames = staticmethod(getOpenFileNames)
    QFileDialog.getSaveFileName  = staticmethod(getSaveFileName)
