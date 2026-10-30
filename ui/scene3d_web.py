"""ui/scene3d_web.py — Hôte web de l'onglet « 3D » (moteur d'ARKLIGHT dans PANDORA).

Demande Matthieu (29/10/2026) : un vrai outil 3D pour la lumière, la mise en scène et
le décor, qui reprend le plan de feu d'ARKLIGHT PC. La vue 3D d'ARKLIGHT (three.js) est
reprise À L'IDENTIQUE (arklight_engine/, voir tools/update_arklight_engine.py) et
affichée dans un QWebEngineView. Ce module :

  - déclare le schéma `pandora3d:` (À FAIRE AVANT la QApplication : `register_scheme()`
    est appelé par main.py) et sert, sans aucun serveur réseau :
        /js/ /shared/ /vendor/ /css/  -> arklight_engine/   (moteur d'ARKLIGHT)
        /pandora/                     -> scene3d_web/       (couche propre à PANDORA)
        /qwebchannel.js               -> ressource de Qt
        /media/<jeton>                -> image du projet autorisée (plan du décor…)
  - fournit `Scene3DView`, le widget qui charge la scène d'un plan, reçoit chacune de
    ses modifications (glisser un projecteur, déplacer un comédien) et pilote la vue.

Le web ne lit ni n'écrit jamais un fichier : tout passe par le pont (QWebChannel) et
c'est Python (core/scene3d) qui enregistre dans le projet.
"""
from __future__ import annotations

import json
import mimetypes
import os
import secrets

from PyQt6.QtCore import (QBuffer, QByteArray, QFile, QIODevice, QObject, Qt, QUrl,
                          pyqtSignal, pyqtSlot)
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from core.paths import assets_root

SCHEME = b"pandora3d"
# Fichiers LIVRÉS (dans _internal/ une fois installé), pas le dossier de données APP_ROOT.
ENGINE_DIR = os.path.join(assets_root(), "arklight_engine")
WEB_DIR = os.path.join(assets_root(), "scene3d_web")
_MIME = {".js": b"text/javascript", ".mjs": b"text/javascript", ".css": b"text/css",
         ".html": b"text/html", ".json": b"application/json", ".png": b"image/png",
         ".jpg": b"image/jpeg", ".jpeg": b"image/jpeg", ".webp": b"image/webp",
         ".svg": b"image/svg+xml", ".glb": b"model/gltf-binary"}

_registered = False
_handler = None          # gardé en vie : le profil ne prend pas possession du gestionnaire
_media: dict[str, str] = {}   # jeton -> fichier image autorisé


def available() -> bool:
    """QtWebEngine présent dans cette installation (sinon l'onglet 3D l'explique)."""
    try:
        import PyQt6.QtWebEngineWidgets  # noqa: F401
        return True
    except Exception:
        return False


def register_scheme() -> None:
    """Déclare `pandora3d:`. Qt l'exige AVANT la création de la QApplication."""
    global _registered
    if _registered or not available():
        return
    from PyQt6.QtCore import QCoreApplication, Qt
    # Fenêtre couverte ou à l'arrière-plan (tableau de bord Windows, autre appli…) : Chromium ne doit
    # ni suspendre la page ni jeter son image, sinon la vue 3D clignote en noir (Matthieu 30/10/2026).
    flags = ("--disable-features=CalculateNativeWinOcclusion --disable-backgrounding-occluded-windows "
             "--disable-renderer-backgrounding --disable-background-timer-throttling")
    cur = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    if flags not in cur:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"{cur} {flags}".strip()
    from PyQt6.QtWebEngineCore import QWebEngineUrlScheme
    s = QWebEngineUrlScheme(SCHEME)
    s.setSyntax(QWebEngineUrlScheme.Syntax.Path)
    # FetchApiAllowed : sans lui, fetch() refuse le schéma (« URL scheme not supported »)
    # — et le chargeur de personnages animés (GLTFLoader) passe par fetch().
    s.setFlags(QWebEngineUrlScheme.Flag.SecureScheme
               | QWebEngineUrlScheme.Flag.LocalAccessAllowed
               | QWebEngineUrlScheme.Flag.CorsEnabled
               | QWebEngineUrlScheme.Flag.FetchApiAllowed)
    QWebEngineUrlScheme.registerScheme(s)
    # contexte OpenGL partagé : demandé par QtWebEngine quand il est chargé après coup
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    _registered = True


def share_image(path: str) -> str:
    """URL `pandora3d:` d'une image du projet (plan du décor…), sans exposer le disque."""
    if not path or not os.path.isfile(path):
        return ""
    for tok, p in _media.items():
        if p == path:
            break
    else:
        tok = secrets.token_hex(8)
        _media[tok] = path
    return f"pandora3d:///media/{tok}{os.path.splitext(path)[1].lower()}"


def resolve(path: str) -> str | None:
    """Fichier servi pour un chemin d'URL, ou None (jamais hors des dossiers prévus)."""
    if path == "/qwebchannel.js":
        return ":qwebchannel"
    if path.startswith("/media/"):
        return _media.get(os.path.splitext(path[len("/media/"):])[0])
    if path.startswith("/pandora/"):
        base, rel = WEB_DIR, path[len("/pandora/"):]
    elif path.startswith(("/js/", "/shared/", "/vendor/", "/css/")):
        base, rel = ENGINE_DIR, path.lstrip("/")
    else:
        return None
    full = os.path.normpath(os.path.join(base, *rel.split("/")))
    if not full.startswith(os.path.normpath(base) + os.sep) or not os.path.isfile(full):
        return None
    return full


def _install_handler(profile) -> None:
    global _handler
    from PyQt6.QtWebEngineCore import QWebEngineUrlSchemeHandler

    class _Handler(QWebEngineUrlSchemeHandler):
        def requestStarted(self, job):   # noqa: N802 (nom imposé par Qt)
            try:
                fp = resolve(job.requestUrl().path())
                if fp == ":qwebchannel":
                    f = QFile(":/qtwebchannel/qwebchannel.js")
                    data = bytes(f.readAll()) if f.open(QIODevice.OpenModeFlag.ReadOnly) else b""
                    mime = b"text/javascript"
                elif fp:
                    with open(fp, "rb") as fh:
                        data = fh.read()
                    ext = os.path.splitext(fp)[1].lower()
                    mime = _MIME.get(ext) or (mimetypes.guess_type(fp)[0] or
                                              "application/octet-stream").encode()
                else:
                    job.fail(job.Error.UrlNotFound)
                    return
                buf = QBuffer(parent=job)
                buf.setData(QByteArray(data))
                buf.open(QIODevice.OpenModeFlag.ReadOnly)
                job.reply(mime, buf)
            except Exception:
                job.fail(job.Error.RequestFailed)

    if _handler is None:
        _handler = _Handler()
    if profile.urlSchemeHandler(SCHEME) is None:
        profile.installUrlSchemeHandler(SCHEME, _handler)


class Bridge(QObject):
    """Pont Python <-> page (QWebChannel). Noms en camelCase : ils sont appelés en JS."""

    # Python -> page
    loadScene = pyqtSignal(str)        # scène complète (JSON) d'un plan
    command = pyqtSignal(str)          # {"op": …} : vue, outil, caméra, temps…
    # page -> Python (relayés par Scene3DView)
    ready_changed = pyqtSignal(dict)
    scene_edited = pyqtSignal(dict)
    selection_changed = pyqtSignal(dict)
    page_event = pyqtSignal(dict)

    @pyqtSlot(str)
    def pageReady(self, info: str) -> None:        # noqa: N802
        self.ready_changed.emit(_loads(info))

    @pyqtSlot(str)
    def sceneEdited(self, scene: str) -> None:     # noqa: N802
        data = _loads(scene)
        if data:
            self.scene_edited.emit(data)

    @pyqtSlot(str)
    def selectionChanged(self, sel: str) -> None:  # noqa: N802
        self.selection_changed.emit(_loads(sel))

    @pyqtSlot(str)
    def emitEvent(self, ev: str) -> None:          # noqa: N802
        self.page_event.emit(_loads(ev))


def _loads(s: str) -> dict:
    try:
        v = json.loads(s or "{}")
        return v if isinstance(v, dict) else {}
    except ValueError:
        return {}


def unavailable_reason() -> str:
    """Pourquoi la vue 3D ne peut pas s'afficher ici ("" si elle peut)."""
    if not available():
        return "La vue 3D a besoin de QtWebEngine, absent de cette installation."
    from PyQt6.QtGui import QGuiApplication
    if (QGuiApplication.platformName() or "").lower() in ("offscreen", "minimal"):
        return "Vue 3D indisponible sans écran (rendu hors écran)."
    return ""


def prepare_window(win) -> None:
    """À appeler AVANT le premier affichage de la fenêtre qui recevra la vue 3D.

    Qt dessine une fenêtre ordinaire en « raster » ; la vue 3D exige la surface de Qt Quick
    (Direct3D sous Windows). La première vue 3D posée dans une fenêtre DÉJÀ affichée oblige
    Qt à la détruire puis à la recréer : PANDORA se fermait et se rouvrait au premier passage
    sur le Plan de feu (Matthieu, 30/10/2026 — mesuré : l'identifiant natif de la fenêtre
    changeait). Un témoin Qt Quick invisible, posé avant l'affichage, la fait naître avec la
    bonne surface : la vue 3D s'y glisse ensuite sans rien recréer. Il ne dessine jamais."""
    if unavailable_reason():
        return
    try:
        from PyQt6.QtQuickWidgets import QQuickWidget
        probe = QQuickWidget(win)
        probe.setFixedSize(1, 1)
        probe.hide()
        win._scene3d_surface = probe
    except Exception:
        pass


class Scene3DView(QWidget):
    """Vue 3D d'un plan. Le moteur web ne démarre qu'au PREMIER AFFICHAGE (une page jamais
    ouverte ne coûte rien) ; sans QtWebEngine ou sans écran : un message, jamais un plantage."""

    ready = pyqtSignal(dict)            # {"catalog": {...}, "gl": bool} une fois la page prête
    scene_edited = pyqtSignal(dict)     # scène complète après une modification dans la vue
    selection_changed = pyqtSignal(dict)
    page_event = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._view = None
        self._ready = False
        self._started = False
        self._pending: str | None = None
        self._queue: list[str] = []
        self._msg = QLabel("")
        self._msg.setWordWrap(True)
        self._msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._msg.hide()
        self._lay.addWidget(self._msg)

    def showEvent(self, e):   # noqa: N802
        super().showEvent(e)
        if not self._started:
            self._started = True
            self._start()

    def _start(self) -> None:
        why = unavailable_reason()
        if why:
            from core.i18n import translate
            self._msg.setText(translate(why))
            self._msg.show()
            return
        from PyQt6.QtWebChannel import QWebChannel
        from PyQt6.QtWebEngineCore import QWebEnginePage
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        self._view = QWebEngineView(self)
        page = QWebEnginePage(self._view)
        _install_handler(page.profile())
        self._view.setPage(page)
        self.bridge = Bridge(self)
        self._channel = QWebChannel(page)
        self._channel.registerObject("pandora", self.bridge)
        page.setWebChannel(self._channel)
        self.bridge.ready_changed.connect(self._on_ready)
        self.bridge.scene_edited.connect(self.scene_edited)
        self.bridge.selection_changed.connect(self.selection_changed)
        self.bridge.page_event.connect(self.page_event)
        self._lay.addWidget(self._view)
        # ?lang= : l'inspecteur d'ARKLIGHT parle la langue de PANDORA
        try:
            from core.i18n import get_lang
            lang = "en" if get_lang() == "en" else "fr"
        except Exception:
            lang = "fr"
        self._view.load(QUrl(f"pandora3d:///pandora/index.html?lang={lang}"))

    # ------------------------------------------------------------------ état
    @property
    def is_ready(self) -> bool:
        return self._ready

    def web_view(self):
        return self._view

    def _on_ready(self, info: dict) -> None:
        self._ready = True
        if self._pending is not None:
            self.bridge.loadScene.emit(self._pending)
            self._pending = None
        for c in self._queue:
            self.bridge.command.emit(c)
        self._queue.clear()
        self.ready.emit(info)

    # ------------------------------------------------------------------ commandes
    def set_scene(self, scene: dict) -> None:
        """Scène à afficher (gardée en attente tant que la page n'est pas prête)."""
        data = json.dumps(scene, ensure_ascii=False)
        if self._ready:
            self.bridge.loadScene.emit(data)
        else:
            self._pending = data
            self._queue.clear()   # les commandes visaient la scène précédente

    def send(self, op: str, **args) -> None:
        """Commande à la page : {"op": "view", "name": "top"}, {"op": "look", "id": …}…"""
        data = json.dumps({"op": op, **args}, ensure_ascii=False)
        if self._ready:
            self.bridge.command.emit(data)
        else:
            self._queue.append(data)

    def run_js(self, code: str, callback=None) -> None:
        """Évaluation directe (tests et captures) ; le pont reste la voie normale."""
        if self._view is not None:
            if callback is None:
                self._view.page().runJavaScript(code)
            else:
                self._view.page().runJavaScript(code, callback)
