import multiprocessing
multiprocessing.freeze_support()  # MUST be first — prevents spawned subprocesses from re-launching the GUI on Windows

import sys

# ── Diagnostic : capture les crashes bas niveau (segfault/abort) que sys.excepthook
#    ne voit pas. faulthandler dumpe la pile de tous les threads dans un fichier. ──
try:
    import faulthandler as _faulthandler, tempfile as _tempfile, os as _os
    _fault_log = open(_os.path.join(_tempfile.gettempdir(), "pandora_fault.log"), "w")
    _faulthandler.enable(file=_fault_log, all_threads=True)
except Exception:
    pass
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtCore import qInstallMessageHandler, QtMsgType
from ui.styles import CP
from ui.splash import SplashWindow
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
                QMessageBox.critical(
                    None, "PANDORA — Erreur",
                    "Une erreur inattendue s'est produite.\n"
                    "L'application reste ouverte — vous pouvez continuer ou la redémarrer.\n\n"
                    f"{exc_type.__name__}: {exc}\n\n"
                    f"Détails enregistrés dans :\n{log_path}",
                )
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

    # ── Flux de démarrage : sélecteur de module → splash → fenêtre ────────────
    #   Chooser (Cinéma | Live) → SplashWindow(mode) → PandoraWindow ou LiveWindow.
    #   Le bouton « retour » du splash ramène au sélecteur.
    from ui.chooser import ChooserWindow

    state = {"chooser": None, "splash": None, "window": None, "opening": False}

    def _show_chooser():
        ch = state["chooser"]
        if ch is not None:
            ch.show()
            ch.raise_()
            ch.activateWindow()

    def _open_project(data: dict):
        if state["opening"]:
            return
        state["opening"] = True
        sp = state["splash"]
        if sp is not None:
            sp.setEnabled(False)
            sp.hide()

        mode = data.get("mode", "cinema")
        if mode == "live":
            from live_window import LiveWindow
            win = LiveWindow(data)
        else:
            win = PandoraWindow(data)

        def _on_switch(new_data: dict):
            win.hide()
            win.deleteLater()
            state["opening"] = False  # ré-entrée autorisée seulement sur changement explicite
            _open_project(new_data)

        win.switch_requested.connect(_on_switch)

        if not icon.isNull():
            win.setWindowIcon(icon)
        state["window"] = win
        win.showMaximized()
        # Force taskbar icon refresh — Windows sometimes ignores the icon set before show()
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(150, lambda: win.setWindowIcon(icon) if not icon.isNull() else None)
        if get_lang() != "fr":
            retranslate_widget(win)
        app._pandora = win

    def _show_splash(mode: str):
        ch = state["chooser"]
        if ch is not None:
            ch.hide()
        sp = SplashWindow(mode)
        if not icon.isNull():
            sp.setWindowIcon(icon)
        if get_lang() != "fr":
            retranslate_widget(sp)
        state["splash"] = sp
        state["opening"] = False

        def _back():
            sp.hide()
            sp.deleteLater()
            state["splash"] = None
            _show_chooser()

        sp.back_requested.connect(_back)
        sp.project_selected.connect(_open_project)
        sp.show()
        sp.raise_()
        sp.activateWindow()

    chooser = ChooserWindow()
    if not icon.isNull():
        chooser.setWindowIcon(icon)
    if get_lang() != "fr":
        retranslate_widget(chooser)
    chooser.cinema_requested.connect(lambda: _show_splash("cinema"))
    chooser.live_requested.connect(lambda: _show_splash("live"))
    chooser.lang_changed.connect(lambda _c: retranslate_widget(chooser))
    state["chooser"] = chooser
    chooser.show()
    app._chooser = chooser

    from api.update_check import UpdateCheckWorker
    from ui.splash import UpdateDialog

    def _on_update_available(version: str, url: str):
        parent = state["window"] or state["splash"] or state["chooser"]
        dlg = UpdateDialog(version, url, parent)
        dlg.exec()

    _upd = UpdateCheckWorker()
    _upd.update_available.connect(_on_update_available)
    _upd.start()
    app._update_worker = _upd

    sys.exit(app.exec())
