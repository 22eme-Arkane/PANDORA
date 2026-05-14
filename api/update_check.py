import json
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal

from core.version import VERSION, GITHUB_RELEASES_URL


def _parse_version(v: str) -> tuple[int, ...]:
    v = v.lstrip("v")
    try:
        return tuple(int(x) for x in v.split("."))
    except (ValueError, AttributeError):
        return (0,)


class UpdateCheckWorker(QThread):
    update_available = pyqtSignal(str, str)  # (version, html_url)
    no_update        = pyqtSignal()
    check_failed     = pyqtSignal()

    def run(self):
        try:
            req = urllib.request.Request(
                GITHUB_RELEASES_URL,
                headers={"User-Agent": "PANDORA-UpdateCheck/1.0"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())
            tag = data.get("tag_name", "")
            url = data.get("html_url", "")
            if not tag:
                self.no_update.emit()
                return
            if _parse_version(tag) > _parse_version(VERSION):
                self.update_available.emit(tag.lstrip("v"), url)
            else:
                self.no_update.emit()
        except Exception:
            self.check_failed.emit()
