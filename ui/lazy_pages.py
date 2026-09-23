"""ui/lazy_pages.py — Pages d'une fenêtre construites à la PREMIÈRE demande.

Mesuré le 24/09/2026 (instrumentation headless du vrai chemin d'ouverture,
projet de 80 fichiers) : construire d'avance les treize pages et les treize
onglets du Studio coûtait ~7 s de construction (3 600 addWidget), puis 3 s de
premier `setCurrentWidget` et 9 s de premier affichage — la mise en page et le
polissage de style de TOUT l'arbre, y compris ce que l'utilisateur ne verra
peut-être jamais dans la session. À l'ouverture, seule la page d'accueil est
construite ; les autres le sont au premier clic, avec le curseur d'attente
(le Studio ~3,5 s, les autres pages quelques dixièmes).

`LazyPages` EST un dict : il ne contient que les pages construites. Mais
`pages["x"]`, `pages.get("x")` et `"x" in pages` construisent à la demande
via la fabrique, pour que le code existant (`self._pages.get(key)`) reste tel
quel. Itérer ne construit rien — on ne parcourt que ce qui existe ; pour
tout construire (harnais), `build_all()`.

Module NEUTRE : utilisé tel quel par la fenêtre Cinéma et la fenêtre Live.
"""

from __future__ import annotations

from typing import Callable


class LazyPages(dict):
    def __init__(self, factories: dict[str, Callable[[], object]],
                 on_built: Callable[[str, object], None],
                 aliases: dict[str, str] | None = None):
        super().__init__()
        self._factories = dict(factories)
        self._aliases = dict(aliases or {})
        self._on_built = on_built          # page fraîche → pose dans la pile, traduction
        self._building: set[str] = set()

    # ── Ce que le dict fait de plus ──────────────────────────────────────────

    def __missing__(self, key):
        page = self.build(key)
        if page is None:
            raise KeyError(key)
        return page

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key):
        k = self._aliases.get(key, key)
        return dict.__contains__(self, k) or k in self._factories

    # ── Construction ─────────────────────────────────────────────────────────

    def keys_all(self) -> list[str]:
        """Toutes les clés servables, construites ou non (alias compris)."""
        return list(self._factories) + list(self._aliases)

    def is_built(self, key) -> bool:
        return dict.__contains__(self, self._aliases.get(key, key))

    def build(self, key):
        """La page `key`, construite si besoin ; None si la clé est inconnue."""
        k = self._aliases.get(key, key)
        if dict.__contains__(self, k):
            return dict.__getitem__(self, k)
        factory = self._factories.get(k)
        if factory is None or k in self._building:
            return None
        self._building.add(k)
        try:
            page = _with_wait_cursor(factory)
            dict.__setitem__(self, k, page)
            self._on_built(k, page)
        finally:
            self._building.discard(k)
        return page

    def build_all(self) -> None:
        for k in list(self._factories):
            self.build(k)


def _with_wait_cursor(factory):
    """Curseur d'attente pendant la construction (quelques dixièmes à
    quelques secondes) — sans QApplication (module importé hors UI), on
    construit simplement."""
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
    except Exception:
        app = None
    if app is None:
        return factory()
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        return factory()
    finally:
        QApplication.restoreOverrideCursor()
