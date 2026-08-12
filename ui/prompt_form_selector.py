"""
ui/prompt_form_selector.py — Sélecteur « Forme du prompt » de la barre Storyboard.

Sert à COMPARER deux écritures du même plan : fiche technique étiquetée contre
phrase de réalisateur. On génère un plan, on bascule, on régénère, on regarde.

Composant NEUTRE (ni Cinéma ni Live) : les deux barres l'instancient telle
quelle. La logique et la persistance vivent dans `core/prompt_form`.

Le libellé annonce l'ESSAI quand une forme est forcée — sinon on oublie qu'un
réglage de test est resté actif et on croit juger le moteur.
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox

from core import prompt_form as _pf
from core.i18n import translate
from ui.styles import CP


class PromptFormSelector(QWidget):
    """Combo compacte. Émet `changed(str)` avec la clé de forme retenue."""

    changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(7)

        self._lbl = QLabel(translate("Forme du prompt"))
        self._lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:11px;background:transparent;")
        lay.addWidget(self._lbl)

        self._combo = QComboBox()
        self._combo.setFixedHeight(32)
        self._combo.setMinimumWidth(210)
        self._combo.setCursor(Qt.CursorShape.PointingHandCursor)
        for key, label, desc in _pf.FORMS:
            self._combo.addItem(translate(label), key)
            self._combo.setItemData(self._combo.count() - 1,
                                    translate(desc), Qt.ItemDataRole.ToolTipRole)
        lay.addWidget(self._combo)

        self._flag = QLabel()
        self._flag.setStyleSheet("background:transparent;")
        lay.addWidget(self._flag)

        self.reload()
        self._combo.currentIndexChanged.connect(self._on_changed)

    # ── État ────────────────────────────────────────────────────────────────

    def reload(self):
        """Relit le réglage du projet (à appeler au changement de projet)."""
        cur = _pf.get_form()
        idx = self._combo.findData(cur)
        if idx >= 0:
            self._combo.blockSignals(True)
            self._combo.setCurrentIndex(idx)
            self._combo.blockSignals(False)
        self._restyle(cur)

    def _restyle(self, key: str):
        forced = key != _pf.AUTO
        # Un essai en cours doit se VOIR : sinon on oublie qu'une forme est
        # imposée et on attribue le résultat au moteur.
        border = CP["accent"] if forced else CP["border"]
        self._combo.setStyleSheet(
            f"QComboBox{{background:{CP['bg2']};border:1px solid {border};"
            f"border-radius:7px;color:{CP['text_primary']};font-size:11px;"
            f"font-weight:600;padding:0 10px;}}"
            f"QComboBox::drop-down{{border:none;width:18px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg2']};"
            f"border:1px solid {CP['border_bright']};"
            f"selection-background-color:{CP['accent_dim']};"
            f"color:{CP['text_primary']};font-size:11px;padding:4px;}}"
        )
        self._flag.setText(translate("essai") if forced else "")
        self._flag.setStyleSheet(
            f"color:{CP['accent']};font-size:10px;font-weight:700;"
            f"background:transparent;"
        )
        self.setToolTip(_pf.description_of(key))

    def _on_changed(self, _idx: int):
        key = self._combo.currentData() or _pf.AUTO
        saved = _pf.set_form(key)
        self._restyle(saved)
        self.changed.emit(saved)

    def current_form(self) -> str:
        return self._combo.currentData() or _pf.AUTO
