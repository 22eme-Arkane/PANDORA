import multiprocessing
multiprocessing.freeze_support()  # MUST be first — prevents spawned subprocesses from re-launching the GUI on Windows

import sys

# ── Diagnostic : capture les crashes bas niveau (segfault/abort) que sys.excepthook
#    ne voit pas. faulthandler dumpe la pile de tous les threads dans un fichier. ──
try:
    import faulthandler as _faulthandler, tempfile as _tempfile, os as _os
    # ⚠ Mode APPEND, jamais « w » : le fichier était remis à zéro à CHAQUE
    # lancement, si bien qu'une fermeture inexpliquée effaçait sa propre preuve
    # dès que l'utilisateur relançait l'application (constat 2026-07-25 : arrêt
    # silencieux à la création d'un projet, journal vide au moment de l'analyse).
    # Un en-tête horodaté sépare les sessions.
    _fault_log = open(_os.path.join(_tempfile.gettempdir(), "pandora_fault.log"),
                      "a", encoding="utf-8", errors="replace")
    try:
        import datetime as _dt
        from core.version import VERSION as _V
        _fault_log.write(f"\n===== session {_dt.datetime.now().isoformat()} "
                         f"· PANDORA {_V} =====\n")
        _fault_log.flush()
    except Exception:
        pass
    _faulthandler.enable(file=_fault_log, all_threads=True)
except Exception:
    pass
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtCore import qInstallMessageHandler, QtMsgType
from ui.styles import CP
from ui.start_page import StartPage
from ui.pandora_window import PandoraWindow


def _qt_msg_handler(msg_type: QtMsgType, context, message: str):
    """Suppress known Qt6 compound-widget stylesheet warnings (cosmetic, not functional)."""
    if "Could not parse stylesheet" in message:
        return
    if "Unknown property cursor" in message:
        return
    if msg_type == QtMsgType.QtDebugMsg:
        return
    print(message, file=sys.stderr)


def _install_excepthook():
    """Filet de sécurité : capture toute exception non gérée (y compris dans les slots Qt),
    la logge dans un fichier, et affiche une erreur — au lieu de laisser PyQt6 fermer l'app."""
    import traceback, datetime, tempfile, os as _os
    log_path = _os.path.join(tempfile.gettempdir(), "pandora_crash.log")

    def _hook(exc_type, exc, tb):
        # Ctrl+C et sys.exit() ne sont PAS des plantages : Python lui-même les
        # écarte dans son excepthook par défaut. Les traiter comme le reste
        # affichait « Une erreur inattendue s'est produite » et écrivait un
        # rapport de crash pour un arrêt DEMANDÉ par l'utilisateur (constat
        # Matthieu 2026-07-27, capture à l'appui). On sort proprement, sans
        # journal et sans fenêtre.
        if issubclass(exc_type, KeyboardInterrupt):
            try:
                print("\nInterruption clavier — fermeture de PANDORA.",
                      file=sys.stderr)
            except Exception:
                pass
            try:
                from PyQt6.QtWidgets import QApplication as _QA
                if _QA.instance() is not None:
                    _QA.instance().quit()
            except Exception:
                pass
            return
        if issubclass(exc_type, SystemExit):
            return

        text = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n===== {datetime.datetime.now().isoformat()} =====\n{text}\n")
        except Exception:
            pass
        try:
            print(text, file=sys.stderr)
        except Exception:
            pass
        try:
            from PyQt6.QtWidgets import QApplication as _QA, QMessageBox
            if _QA.instance() is not None:
                box = QMessageBox(
                    QMessageBox.Icon.Critical, "PANDORA — Erreur",
                    "Une erreur inattendue s'est produite.\n"
                    "L'application reste ouverte — vous pouvez continuer ou la redémarrer.\n\n"
                    f"{exc_type.__name__}: {exc}\n\n"
                    f"Détails enregistrés dans :\n{log_path}",
                )
                box.setDetailedText(text)   # « Afficher les détails » = la trace complète
                box.addButton("Fermer", QMessageBox.ButtonRole.RejectRole)
                # Envoi du rapport à 22eme ARKANE (Supabase, insertion seule) — bouton
                # présent seulement si le serveur est configuré. Appel BLOQUANT court :
                # au crash, démarrer un QThread n'est plus fiable.
                btn_send = None
                try:
                    from core.support_backend import is_configured as _sb_ok
                    if _sb_ok():
                        btn_send = box.addButton("✉  Envoyer le rapport",
                                                 QMessageBox.ButtonRole.AcceptRole)
                except Exception:
                    pass
                box.exec()
                if btn_send is not None and box.clickedButton() is btn_send:
                    try:
                        from core.support_backend import submit_report
                        submit_report("crash", f"{exc_type.__name__}: {exc}", log=text)
                        QMessageBox.information(
                            None, "PANDORA — Rapport envoyé",
                            "Merci ! Le rapport de crash a été transmis à 22eme ARKANE.")
                    except Exception as send_err:
                        QMessageBox.warning(
                            None, "PANDORA — Envoi impossible",
                            f"Le rapport n'a pas pu être envoyé :\n{send_err}\n\n"
                            f"Le log reste disponible ici :\n{log_path}")
        except Exception:
            pass

    sys.excepthook = _hook


def _set_palette(app: QApplication):
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor(CP["bg0"]))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor(CP["text_primary"]))
    palette.setColor(QPalette.ColorRole.Base,            QColor(CP["bg2"]))
    palette.setColor(QPalette.ColorRole.Text,            QColor(CP["text_primary"]))
    palette.setColor(QPalette.ColorRole.Button,          QColor(CP["bg3"]))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor(CP["text_primary"]))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor(CP["accent"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#07080f"))
    app.setPalette(palette)


def _force_qt_file_dialogs():
    """Dialogues de fichiers Qt NON-NATIFS + VIGNETTES d'images (voir ui/file_dialogs).

    Non-natif : le dialogue NATIF Windows passe par le shell COM/OLE ; sur certaines
    configs cela plante (vu dans %TEMP%\\pandora_fault.log :
    RPC_E_CANTCALLOUT_ININPUTSYNCCALL 0x8001010d / RPC_E_DISCONNECTED 0x80010108) à
    l'ouverture d'un import de fichiers. Le dialogue Qt n'utilise pas COM → plus de
    crash. Vignettes : un QFileIconProvider affiche l'aperçu des images dans
    l'explorateur (plus pratique pour choisir une image de référence). Les 3 méthodes
    statiques de QFileDialog sont remplacées par des versions instance — reste inchangé.
    """
    try:
        from ui.file_dialogs import install_thumbnail_file_dialogs
        install_thumbnail_file_dialogs()
    except Exception:
        pass


if __name__ == "__main__":
    _install_excepthook()

    # Restaurer la langue préférée avant toute création de widget
    from core.i18n import load_saved_lang, get_lang, retranslate_widget
    load_saved_lang()

    # Windows : déclare un AppUserModelID pour que la barre des tâches
    # utilise notre icône plutôt que l'icône Python générique
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "com.22eme-arkane.pandora.1"
        )
    except Exception:
        pass

    qInstallMessageHandler(_qt_msg_handler)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from ui.input_policy import install_wheel_scroll_policy
    install_wheel_scroll_policy(app)
    _force_qt_file_dialogs()   # dialogues Qt non-natifs → évite les crashs COM Windows
    _set_palette(app)

    from ui.icons import app_icon
    icon = app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    # Vérification EULA — obligatoire au premier lancement
    from core.config import load_config, save_config
    _cfg = load_config()
    if not _cfg.get("eula_accepted", False):
        from ui.dialog_eula import EulaDialog
        _eula = EulaDialog(mode="accept")
        if _eula.exec() != EulaDialog.DialogCode.Accepted:
            sys.exit(0)
        _cfg["eula_accepted"] = True
        save_config(_cfg)

    # ── Flux de démarrage unifié ───────────────────────────────────────────────
    #   Cinéma / Live restent sur la même page : la sélection choisit le mode du
    #   prochain projet et filtre les récents, sans écran intermédiaire.
    from core.edition import is_cinema_only
    _CINEMA_ONLY = is_cinema_only()

    state = {"start": None, "window": None, "opening": False}

    def _open_project(data: dict):
        if state["opening"]:
            return
        state["opening"] = True
        start_page = state["start"]
        if start_page is not None:
            start_page.setEnabled(False)
            start_page.hide()

        mode = data.get("mode", "cinema")
        # Splash de chargement (2026-07-23) : la fenêtre est RECRÉÉE par
        # conception (état propre entre projets) — le splash montre que rien
        # n'a planté pendant la construction (pulse() anime entre les pages).
        from ui.loading_splash import open_splash, close_splash
        _pname = (data.get("name") or "").strip()
        if _pname:
            _splash_txt = f"Ouverture de « {_pname} »…"
        elif mode == "live":
            _splash_txt = "Ouverture de PANDORA | Live…"
        else:
            _splash_txt = "Ouverture de PANDORA Cinéma…"
        open_splash(_splash_txt)
        try:
            if mode == "live" and not _CINEMA_ONLY:
                from live_window import LiveWindow
                win = LiveWindow(data)
            else:
                win = PandoraWindow(data)
        except Exception:
            close_splash()
            raise

        # ⚠ CRASH À LA CRÉATION D'UN PROJET (constat Matthieu 2026-07-25) : la
        # fenêtre se fermait sans message et l'application ne revenait pas — alors
        # que le projet, lui, était bien créé.
        #
        # Cause : ce signal est émis par un widget ENFANT de `win` — le bouton
        # « Nouveau projet » ou une vignette de la page Projets. Détruire `win`
        # ici revient à supprimer l'émetteur PENDANT sa propre émission ; et le
        # splash de chargement ouvert juste après appelle processEvents(), qui
        # exécute la suppression différée séance tenante. Quand la pile remonte,
        # Qt reprend la main sur un objet C++ déjà libéré → arrêt brutal.
        #
        # Correctif : on rend la main à la boucle d'événements AVANT de basculer.
        # L'ancienne fenêtre est masquée tout de suite (rien ne change à l'œil),
        # puis détruite une fois la nouvelle debout, hors de toute émission.
        def _on_switch(new_data: dict):
            from PyQt6.QtCore import QTimer as _QTimer
            win.hide()
            try:
                win.switch_requested.disconnect()
            except TypeError:
                pass

            def _swap():
                state["opening"] = False   # ré-entrée autorisée seulement ici
                try:
                    _open_project(new_data)
                finally:
                    win.deleteLater()

            _QTimer.singleShot(0, _swap)

        win.switch_requested.connect(_on_switch)

        def _return_home():
            from PyQt6.QtCore import QTimer as _QTimer
            win.hide()
            # Même précaution : « retour à l'accueil » est déclenché depuis un
            # bouton de `win`.
            _QTimer.singleShot(0, win.deleteLater)
            state["window"] = None
            state["opening"] = False
            if start_page is not None:
                start_page.setEnabled(True)
                if hasattr(start_page, "refresh"):
                    start_page.refresh()
                start_page.showMaximized()
                start_page.raise_()
                start_page.activateWindow()

        if hasattr(win, "home_requested"):
            win.home_requested.connect(_return_home)

        if not icon.isNull():
            win.setWindowIcon(icon)
        state["window"] = win
        # Lancement depuis la carte Cinéma/Live (sans projet) → arriver sur
        # l'onglet Projets pour ouvrir ou créer (demande Matthieu 2026-07-23).
        if data.get("_start_on_projects"):
            try:
                win._navigate("projects")
            except Exception:
                pass
        win.showMaximized()
        close_splash()
        # Force taskbar icon refresh — Windows sometimes ignores the icon set before show()
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(150, lambda: win.setWindowIcon(icon) if not icon.isNull() else None)
        if get_lang() != "fr":
            retranslate_widget(win)
        app._pandora = win

    # Page unique : Cinéma/Live ne font que changer la sélection et filtrer les
    # récents. Nouveau/Ouvrir mènent ensuite directement au projet.
    start_page = StartPage(allow_live=not _CINEMA_ONLY)
    if not icon.isNull():
        start_page.setWindowIcon(icon)
    start_page.project_selected.connect(_open_project)
    # Clic direct sur une carte Cinéma/Live → fenêtre SANS projet, ouverte sur
    # l'onglet Projets (le choix/création du projet se fait là, 2026-07-23).
    start_page.mode_launched.connect(
        lambda mode: _open_project({"mode": mode, "_start_on_projects": True}))
    state["start"] = start_page
    start_page.show()
    start_page.raise_()
    start_page.activateWindow()
    app._start_page = start_page

    from api.update_check import UpdateCheckWorker
    from ui.splash import UpdateDialog

    def _on_update_available(version: str, url: str):
        parent = state["window"] or state["start"]
        dlg = UpdateDialog(version, url, parent)
        dlg.exec()

    _upd = UpdateCheckWorker()
    _upd.update_available.connect(_on_update_available)
    _upd.start()
    app._update_worker = _upd

    sys.exit(app.exec())
