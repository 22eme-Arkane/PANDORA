"""Fiche latérale repliable + état vide centré des pages éléments (Cinéma).

Demandes Matthieu 2026-07-23 :
- comme la poignée GUIDE : une fiche « FICHE » au bord DROIT de la fenêtre,
  ouverte/refermée par une poignée fléchée, qui montre l'élément sélectionné
  (photo en grand, nom, sous-titre, présence au storyboard, description) ;
- clic sur une carte = sélection (ouvre la fiche) ;
- état vide : titre centré dans la fenêtre + bouton « ⊕ Générer depuis le
  scénario » (disparaît dès qu'il existe des éléments).

Les pages Live héritent automatiquement via leurs alias (page_castings_live…).
"""
import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QScrollArea,
                             QVBoxLayout, QWidget)

from core.i18n import translate
from ui.styles import CP

PANEL_W  = 320
_PHOTO_H = 330


class ElementSidePanel(QWidget):
    """Fiche latérale : photo, nom, sous-titre, stats storyboard, description."""

    def __init__(self, empty_text: str, placeholder: str = "👤"):
        super().__init__()
        self._empty_text = empty_text
        self._placeholder = placeholder
        self._toggle = None
        self.setFixedWidth(PANEL_W)
        # FOND réellement PEINT (retour Matthieu 2026-07-23 : la fiche Décors
        # n'avait pas de fond) : un QWidget n'applique son stylesheet de fond
        # qu'avec WA_StyledBackground + sélecteur ciblé (jamais de règle nue).
        self.setObjectName("ElementSidePanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"QWidget#ElementSidePanel{{background:{CP['bg1']};}}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)

        # ── Ordre 2026-07-23 (retour Matthieu) : NOM, sous-titre, PHOTO,
        # « STORYBOARD » + présence, « DESCRIPTION » + texte. ──
        self._name = QLabel(translate(empty_text))
        self._name.setWordWrap(True)
        self._name.setStyleSheet(
            f"color:{CP['text_primary']};font-size:16px;font-weight:700;background:transparent;"
        )
        lay.addWidget(self._name)

        self._sub = QLabel("")
        self._sub.setWordWrap(True)
        self._sub.setStyleSheet(
            f"color:{CP['accent']};font-size:10px;font-weight:700;background:transparent;"
        )
        lay.addWidget(self._sub)

        self._photo = QLabel(placeholder)
        self._photo.setFixedSize(PANEL_W - 28, _PHOTO_H)
        self._photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._photo.setStyleSheet(
            f"background:{CP['bg3']};border-radius:10px;"
            f"color:{CP['text_dim']};font-size:44px;"
        )
        lay.addWidget(self._photo)

        def _caption(text: str) -> QLabel:
            c = QLabel(text)
            c.setStyleSheet(
                f"color:{CP['text_dim']};font-size:9px;letter-spacing:2px;"
                f"font-family:'Consolas',monospace;font-weight:700;background:transparent;"
            )
            return c

        self._cap_sb = _caption("STORYBOARD")
        lay.addWidget(self._cap_sb)
        self._stats = QLabel("")
        self._stats.setWordWrap(True)
        self._stats.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;"
        )
        lay.addWidget(self._stats)

        self._cap_desc = _caption("DESCRIPTION")
        lay.addWidget(self._cap_desc)
        _scroll = QScrollArea()
        _scroll.setWidgetResizable(True)
        _scroll.setFrameStyle(0)
        _scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self._desc = QLabel("")
        self._desc.setWordWrap(True)
        self._desc.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._desc.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._desc.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;"
        )
        _scroll.setWidget(self._desc)
        lay.addWidget(_scroll, 1)

        self.setVisible(False)   # fermée par défaut (rien de sélectionné)

    # ── API ───────────────────────────────────────────────────────────────────

    def show_item(self, *, name: str, subtitle: str = "", description: str = "",
                  stats: str = "", image_path: str = ""):
        w, h = PANEL_W - 28, _PHOTO_H
        # Photo de la fiche mise en cache, décodée à la taille du panneau
        # (audit 2026-07-31) : chaque clic sur une carte redéveloppait le
        # fichier d'origine — une fiche de personnage fait 2160×3840 — pour
        # l'afficher dans un panneau de quelques centaines de pixels. C'est ce
        # qui donnait les « 2 ou 3 secondes » ressenties au clic.
        from ui.thumb_cache import card_pixmap, ensure_cache_size
        ensure_cache_size()
        _pix = card_pixmap(image_path, w, h)
        if _pix is not None:
            self._photo.setPixmap(_pix)
        else:
            self._photo.setPixmap(QPixmap())
            self._photo.setText(self._placeholder)
        self._name.setText(name or "—")
        self._sub.setText((subtitle or "").upper())
        self._stats.setText(stats or "")
        self._stats.setVisible(bool(stats))
        self._cap_sb.setVisible(bool(stats))   # HMC : pas de présence storyboard
        self._desc.setText((description or "").strip() or translate("Aucune description."))
        self.reveal()

    def clear(self):
        self._photo.setPixmap(QPixmap())
        self._photo.setText(self._placeholder)
        self._name.setText(translate(self._empty_text))
        self._sub.setText("")
        self._stats.setText("")
        self._desc.setText("")

    def reveal(self):
        """La sélection OUVRE la fiche si elle est fermée (poignée pour replier)."""
        if not self.isVisible() and self._toggle is not None:
            self._toggle._open = True
            self._toggle._update_arrow()
            self.setVisible(True)


def attach_side_panel(page, content: QWidget, empty_text: str,
                      placeholder: str = "👤") -> ElementSidePanel:
    """Réorganise `page` (qui ne doit PAS encore avoir de layout) en
    [ contenu | fiche | poignée FICHE ] — même mécanique que GUIDE/ASSISTANT."""
    from ui.page_scenario import _PanelToggle
    outer = QHBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)
    outer.addWidget(content, 1)
    panel = ElementSidePanel(empty_text, placeholder)
    outer.addWidget(panel)
    toggle = _PanelToggle("FICHE", opened=False)
    toggle.toggled.connect(panel.setVisible)
    outer.addWidget(toggle)
    panel._toggle = toggle
    return panel


# ── Présence au storyboard ────────────────────────────────────────────────────

def storyboard_stats(kind: str, data: dict) -> str:
    """« 🎬 N plan(s) au storyboard · M séquence(s) » pour un élément — champs des
    shots : character_ids/names, decor_id/name, accessory_names, vehicle_ids/names.
    HMC : pas de colonne au storyboard → chaîne vide."""
    if kind == "hmc":
        return ""
    try:
        import core.storyboard as sb
        shots = sb.list_shots()
    except Exception:
        return ""
    eid = data.get("id", "")
    name = (data.get("name") or "").strip().lower()

    def _match(s: dict) -> bool:
        if kind == "character":
            ids, names = s.get("character_ids") or [], s.get("character_names") or []
        elif kind == "decor":
            return bool((eid and s.get("decor_id") == eid)
                        or (name and (s.get("decor_name") or "").strip().lower() == name))
        elif kind == "accessory":
            ids, names = s.get("accessory_ids") or [], s.get("accessory_names") or []
        elif kind == "vehicle":
            ids, names = s.get("vehicle_ids") or [], s.get("vehicle_names") or []
        else:
            return False
        return bool((eid and eid in ids)
                    or (name and name in [str(x).strip().lower() for x in names]))

    n, seqs = 0, set()
    for s in shots:
        if _match(s):
            n += 1
            sq = s.get("seq_num")
            if sq not in (None, ""):
                seqs.add(sq)
    if not n:
        return translate("Aucun plan au storyboard pour l'instant")
    txt = f"🎬  {n} {translate('plan(s) au storyboard')}"
    if seqs:
        txt += f"  ·  {len(seqs)} {translate('séquence(s)')}"
    return txt


# ── État vide centré + « Générer depuis le scénario » ─────────────────────────

def make_empty_state(text: str, on_generate=None) -> QWidget:
    """Bloc centré dans la fenêtre : message + bouton de génération optionnel.
    Expose `_empty_lbl` et `_empty_gen_btn` (assertions harnais / mises à jour)."""
    w = QWidget()
    w.setStyleSheet("background:transparent;")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(18)
    lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl = QLabel(translate(text))
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setWordWrap(True)
    lbl.setFixedWidth(460)   # largeur définie → heightForWidth déterministe
    lbl.setStyleSheet(
        f"color:{CP['text_dim']};font-size:13px;background:transparent;border:none;")
    lay.addWidget(lbl, 0, Qt.AlignmentFlag.AlignHCenter)
    w._empty_lbl = lbl
    w._empty_gen_btn = None
    if on_generate is not None:
        btn = QPushButton("⊕  " + translate("Générer depuis le scénario"))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(42)
        btn.setStyleSheet(
            f"QPushButton{{background:{CP['accent2']};color:#fff;border:none;"
            f"border-radius:8px;font-size:12px;font-weight:700;padding:0 28px;}}"
            f"QPushButton:hover{{background:#9d8fff;}}"
            f"QPushButton:pressed{{background:#6a5acd;}}")
        btn.clicked.connect(on_generate)
        lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
        w._empty_gen_btn = btn
    return w


def open_generate_from_scenario(page, kind: str):
    """Ouvre le dialogue d'extraction+génération du scénario courant pour `kind`
    (decor / accessory / hmc / vehicle / character) puis rafraîchit la page."""
    from PyQt6.QtWidgets import QMessageBox
    import core.scenario as scenario_api
    scenarios = scenario_api.list_scenarios()
    text = ""
    if scenarios:
        sc = scenarios[0]
        text = (sc.get("formatted_content") or sc.get("raw_content") or "").strip()
    if not text:
        QMessageBox.information(
            page, translate("Aucun scénario"),
            translate("Aucun scénario disponible.\nÉcris d'abord un scénario dans l'onglet Scénario."))
        return
    from ui.dialog_extract_generate import ExtractGenerateDialog
    factory = {
        "character": ExtractGenerateDialog.for_characters,
        "decor":     ExtractGenerateDialog.for_decors,
        "accessory": ExtractGenerateDialog.for_accessories,
        "hmc":       ExtractGenerateDialog.for_hmc,
        "vehicle":   ExtractGenerateDialog.for_vehicles,
    }.get(kind)
    if factory is None:
        return
    dlg = factory(text, page)
    dlg.exec()
    try:
        page.refresh()
    except Exception:
        pass
