import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtCore import qInstallMessageHandler, QtMsgType
from ui.styles import CP
from ui.chooser import ChooserWindow
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

    chooser = ChooserWindow()
    if not icon.isNull():
        chooser.setWindowIcon(icon)
    if get_lang() != "fr":
        retranslate_widget(chooser)

    def _on_chooser_lang(lang: str):
        retranslate_widget(chooser)

    chooser.lang_changed.connect(_on_chooser_lang)

    def _show_splash(mode: str):
        chooser.hide()
        splash = SplashWindow(mode)
        if not icon.isNull():
            splash.setWindowIcon(icon)
        if get_lang() != "fr":
            retranslate_widget(splash)

        def _on_back():
            splash.hide()
            splash.deleteLater()
            chooser.show()
            app._splash = None

        def _on_project(data: dict):
            splash.hide()
            win = PandoraWindow(data)

            def _on_switch(new_data: dict):
                win.hide()
                win.deleteLater()
                _on_project(new_data)

            win.switch_requested.connect(_on_switch)
            win.showMaximized()
            if get_lang() != "fr":
                retranslate_widget(win)
            app._pandora = win

        def _on_live_project(_data: dict):
            splash.hide()
            from live_window import LiveWindow
            live = LiveWindow()
            live.showMaximized()
            app._live = live

        splash.back_requested.connect(_on_back)
        if mode == "cinema":
            splash.project_selected.connect(_on_project)
        else:
            splash.project_selected.connect(_on_live_project)

        splash.show()
        app._splash = splash

    chooser.cinema_requested.connect(lambda: _show_splash("cinema"))
    chooser.live_requested.connect(lambda: _show_splash("live"))
    chooser.show()

    sys.exit(app.exec())
