"""
ui/dialog_projector.py — Choix d'un projecteur pour le Plan de feu.

Fenêtre à 2 colonnes : FAMILLE (panneau LED, Fresnel, Tube…) → MODÈLES réels
(SkyPanel, Titan…). Plus un sélecteur de RÔLE (key, fill, back…) indépendant
(un même projecteur peut servir de key ou de fill).

result() → {"role", "family", "model", "name"} ou None si annulé.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QListWidget, QListWidgetItem, QLineEdit,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from ui.styles import CP
from ui.icons import load_icon
from core.i18n import translate
import core.projectors as proj


class ProjectorDialog(QDialog):
    def __init__(self, parent=None, role="key", family="", model=""):
        super().__init__(parent)
        self.setWindowTitle(translate("Choisir un projecteur"))
        self.setMinimumSize(640, 460)
        self.setStyleSheet(f"background:{CP['bg1']};")
        self._result = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        title = QLabel("💡  " + translate("Choisir un projecteur"))
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:15px;font-weight:700;background:transparent;")
        root.addWidget(title)

        # ── Rôle (fonction) ───────────────────────────────────────────────────
        role_row = QHBoxLayout()
        role_lbl = QLabel(translate("Rôle :"))
        role_lbl.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;background:transparent;")
        role_row.addWidget(role_lbl)
        self._role = QComboBox()
        for code, label in proj.PROJECTOR_ROLES:
            self._role.addItem(label, code)
        i = self._role.findData(role)
        if i >= 0:
            self._role.setCurrentIndex(i)
        self._role.setStyleSheet(
            f"QComboBox{{background:{CP['bg2']};color:{CP['text_primary']};"
            f"border:1px solid {CP['border']};border-radius:6px;padding:6px 10px;font-size:12px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};color:{CP['text_primary']};"
            f"selection-background-color:{CP['accent_dim']};}}")
        role_row.addWidget(self._role, 1)
        root.addLayout(role_row)

        # ── 2 colonnes : Famille → Modèles ────────────────────────────────────
        cols = QHBoxLayout()
        cols.setSpacing(10)

        col1 = QVBoxLayout(); col1.setSpacing(4)
        col1.addWidget(self._col_label(translate("Famille")))
        self._fam_list = QListWidget()
        self._fam_list.setStyleSheet(self._list_style())
        self._fam_list.setIconSize(QSize(26, 26))
        for code, label in proj.families():
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, code)
            _icf = proj.family_icon(code)
            if _icf:
                _pm = load_icon(_icf, size=26)
                if not _pm.isNull():
                    it.setIcon(QIcon(_pm))
            self._fam_list.addItem(it)
        self._fam_list.currentRowChanged.connect(self._on_family)
        col1.addWidget(self._fam_list, 1)
        cols.addLayout(col1, 1)

        col2 = QVBoxLayout(); col2.setSpacing(4)
        col2.addWidget(self._col_label(translate("Modèle")))
        self._mod_list = QListWidget()
        self._mod_list.setStyleSheet(self._list_style())
        self._mod_list.itemDoubleClicked.connect(lambda _: self._accept())
        col2.addWidget(self._mod_list, 1)
        cols.addLayout(col2, 1)
        root.addLayout(cols, 1)

        # ── Nom libre (étiquette du jeton) ────────────────────────────────────
        name_row = QHBoxLayout()
        name_lbl = QLabel(translate("Nom :"))
        name_lbl.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;background:transparent;")
        name_row.addWidget(name_lbl)
        self._name = QLineEdit()
        self._name.setPlaceholderText(translate("Nom affiché (laisser vide = modèle)"))
        self._name.setStyleSheet(
            f"QLineEdit{{background:{CP['bg2']};color:{CP['text_primary']};"
            f"border:1px solid {CP['border']};border-radius:6px;padding:6px 10px;font-size:12px;}}")
        name_row.addWidget(self._name, 1)
        root.addLayout(name_row)

        # ── Boutons ───────────────────────────────────────────────────────────
        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton(translate("Annuler"))
        cancel.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;font-size:12px;padding:7px 16px;}}"
            f"QPushButton:hover{{background:{CP['bg2']};}}")
        cancel.clicked.connect(self.reject)
        ok = QPushButton(translate("Valider"))
        ok.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;border:none;"
            f"border-radius:7px;font-size:12px;font-weight:700;padding:7px 18px;}}"
            f"QPushButton:hover{{background:#6eded6;}}")
        ok.clicked.connect(self._accept)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        root.addLayout(btns)

        # Sélection initiale
        start = 0
        if family:
            for r in range(self._fam_list.count()):
                if self._fam_list.item(r).data(Qt.ItemDataRole.UserRole) == family:
                    start = r
                    break
        self._fam_list.setCurrentRow(start)
        if model:
            for r in range(self._mod_list.count()):
                if self._mod_list.item(r).text() == model:
                    self._mod_list.setCurrentRow(r)
                    break

    def _col_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-weight:700;letter-spacing:1px;"
            f"background:transparent;")
        return lbl

    def _list_style(self):
        return (
            f"QListWidget{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:12px;padding:4px;}}"
            f"QListWidget::item{{padding:6px 8px;border-radius:5px;}}"
            f"QListWidget::item:selected{{background:{CP['accent_dim']};color:#07080f;}}")

    def _on_family(self, row: int):
        self._mod_list.clear()
        if row < 0:
            return
        code = self._fam_list.item(row).data(Qt.ItemDataRole.UserRole)
        for m in proj.models(code):
            self._mod_list.addItem(QListWidgetItem(m))
        if self._mod_list.count():
            self._mod_list.setCurrentRow(0)

    def _accept(self):
        fam_item = self._fam_list.currentItem()
        mod_item = self._mod_list.currentItem()
        if not fam_item or not mod_item:
            return
        family = fam_item.data(Qt.ItemDataRole.UserRole)
        model  = mod_item.text()
        self._result = {
            "role":   self._role.currentData(),
            "family": family,
            "model":  model,
            "name":   self._name.text().strip() or model,
        }
        self.accept()

    def result_data(self):
        return self._result
