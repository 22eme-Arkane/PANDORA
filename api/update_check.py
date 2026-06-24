import json
import re
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal

from core.version import VERSION, GITHUB_RELEASES_URL


def _parse_version(v: str) -> tuple[int, ...]:
    """'v1.2.3' / '1.2.0-bêta' → (1, 2, 3) / (1, 2, 0).

    Les suffixes pré-release (-bêta, -rc1, …) sont ignorés pour la comparaison :
    une bêta de 1.2.0 reste la version 1.2.0 face au dépôt GitHub (sinon l'app se
    croit périmée et déclenche à tort la bannière de mise à jour)."""
    parts: list[int] = []
    for chunk in (v or "").lstrip("vV").strip().split("."):
        m = re.match(r"\d+", chunk)
        if not m:
            break
        parts.append(int(m.group()))
    return tuple(parts) if parts else (0,)


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
