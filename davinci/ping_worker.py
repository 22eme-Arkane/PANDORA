"""Worker QThread de ping du pont DaVinci — partagé par DaVinciPanel et TabDavinciEdit."""

from PyQt6.QtCore import QThread, pyqtSignal


class BridgePingWorker(QThread):
    """Ping asynchrone du pont (davinci.bridge) : met à jour l'état partagé
    `resolve` (version du pont, API, projet, timeline) puis émet
    result(connecté, nom de la timeline). Durée : ≤ 1 s si le pont ne tourne
    pas (davinci.bridge.CONNECT_TIMEOUT)."""
    result = pyqtSignal(bool, str)

    def run(self):
        connected, timeline = False, ""
        try:
            from davinci.bridge import resolve
            connected = resolve.ping(timeout=1.5)
            if connected:
                timeline = resolve.fetch_status().get("timeline", "")
        except Exception:
            connected = False
        self.result.emit(connected, str(timeline or ""))
        try:
            from davinci.jobs import notify
            notify()
        except Exception:
            pass
