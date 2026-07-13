"""api/report.py — Worker d'envoi des avis / bugs vers Supabase (hors thread UI).

Utilisé par la fenêtre « Nous contacter » (ui/dialog_contact.py). Le rapport de
CRASH, lui, part en appel bloquant court depuis main.py (au crash, démarrer un
QThread n'est plus fiable). Signaux : done / failed — jamais « finished » (masquerait
le signal natif QThread).
"""

from PyQt6.QtCore import QThread, pyqtSignal


class SendReportWorker(QThread):
    done   = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, kind: str, message: str, email: str = "", log: str = ""):
        super().__init__()
        self._kind    = kind
        self._message = message
        self._email   = email
        self._log     = log

    def run(self):
        try:
            from core.support_backend import submit_report
            submit_report(self._kind, self._message, self._email, self._log)
            self.done.emit()
        except Exception as e:
            from core.worker import humanize_api_error
            self.failed.emit(humanize_api_error(str(e)))
