"""Politique d'entrée globale de PANDORA.

La molette et le défilement à deux doigts servent exclusivement à parcourir
les pages. Qt modifie normalement la valeur d'un QComboBox, d'un spinbox ou
d'un curseur lorsque le pointeur les survole ; sur un pavé tactile, ce
comportement provoque facilement des changements involontaires.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtWidgets import (
    QAbstractScrollArea, QAbstractSpinBox, QApplication, QComboBox, QDial,
    QSlider, QWidget,
)


class WheelScrollOnlyFilter(QObject):
    """Empêche la molette de modifier un contrôle et fait défiler son panneau."""

    _VALUE_WIDGETS = (QComboBox, QAbstractSpinBox, QSlider, QDial)

    @staticmethod
    def _scroll_area(widget: QWidget | None) -> QAbstractScrollArea | None:
        current = widget
        while current is not None:
            if isinstance(current, QAbstractScrollArea):
                return current
            current = current.parentWidget()
        return None

    def eventFilter(self, watched, event):
        if event.type() != QEvent.Type.Wheel or not isinstance(watched, self._VALUE_WIDGETS):
            return super().eventFilter(watched, event)

        area = self._scroll_area(watched.parentWidget())
        if area is not None:
            bar = area.verticalScrollBar()
            pixel_y = event.pixelDelta().y()
            angle_y = event.angleDelta().y()
            if pixel_y:
                delta = pixel_y
            elif angle_y:
                notches = angle_y / 120.0
                delta = int(notches * max(24, bar.singleStep() * 3))
            else:
                delta = 0
            if delta:
                bar.setValue(bar.value() - delta)

        # Même sans panneau défilable, l'événement est consommé : la valeur du
        # contrôle ne doit jamais changer sous l'effet de la molette.
        event.accept()
        return True


def install_wheel_scroll_policy(app: QApplication) -> WheelScrollOnlyFilter:
    """Installe une seule instance du filtre sur l'application Qt."""
    existing = getattr(app, "_pandora_wheel_scroll_filter", None)
    if existing is not None:
        return existing
    policy = WheelScrollOnlyFilter(app)
    app.installEventFilter(policy)
    app._pandora_wheel_scroll_filter = policy
    return policy
