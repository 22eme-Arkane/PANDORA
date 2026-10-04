"""
Exécuter une fonction HORS du thread de l'interface (module neutre : Cinéma et Live).

    run_task(fn, on_done, *args)   →   on_done(résultat) sur le thread de l'interface

Règles maison (CLAUDE.md) : signal `done` (jamais `finished`, qui masquerait le
signal natif de QThread), référence gardée jusqu'à la fin du thread (un QThread
ramassé en cours d'exécution fait planter l'application), aucune exception ne
sort du thread (elle devient {"ok": False, "error": message}).
"""

from PyQt6.QtCore import QThread, pyqtSignal


class BackgroundTask(QThread):
    done = pyqtSignal(object)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn, self._args, self._kwargs = fn, args, kwargs

    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:
            result = {"ok": False, "error": str(exc) or exc.__class__.__name__}
        self.done.emit(result)


_RUNNING: set = set()


def run_task(fn, on_done=None, *args, **kwargs) -> BackgroundTask:
    """Lance `fn(*args, **kwargs)` dans un thread ; `on_done(résultat)` est appelé
    sur le thread de l'interface. Une exception dans `on_done` est absorbée (un
    slot qui lève ferait tout planter)."""
    task = BackgroundTask(fn, *args, **kwargs)
    if on_done is not None:
        def _deliver(result, _cb=on_done):
            try:
                _cb(result)
            except Exception:
                pass
        task.done.connect(_deliver)
    _RUNNING.add(task)
    task.finished.connect(lambda t=task: _RUNNING.discard(t))
    task.start()
    return task
