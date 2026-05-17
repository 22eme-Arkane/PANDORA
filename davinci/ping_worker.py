"""Worker QThread de ping bridge DaVinci — partagé par DaVinciPanel et TabDavinciEdit."""

from PyQt6.QtCore import QThread, pyqtSignal


class BridgePingWorker(QThread):
    """Ping asynchrone du bridge TCP DaVinci (port 19876).
    Émet result(connected: bool, timeline_name: str).
    Durée max : 1 s (timeout court pour ne pas gêner le polling toutes les 5 s).
    """
    result = pyqtSignal(bool, str)

    def run(self):
        try:
            import json, socket
            HOST, PORT = "127.0.0.1", 19876

            def _quick_send(cmd: str) -> object:
                req = json.dumps({"cmd": cmd, "params": {}}) + "\n"
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1.0)           # timeout court pour le polling
                    s.connect((HOST, PORT))
                    s.sendall(req.encode("utf-8"))
                    data = b""
                    while True:
                        chunk = s.recv(4096)
                        if not chunk:
                            break
                        data += chunk
                        if data.endswith(b"\n"):
                            break
                resp = json.loads(data.decode("utf-8"))
                return resp.get("result") if resp.get("ok") else None

            pong = _quick_send("ping")
            if pong == "pong":
                tl = _quick_send("get_timeline_name") or ""
                self.result.emit(True, str(tl))
            else:
                self.result.emit(False, "")
        except Exception:
            self.result.emit(False, "")
