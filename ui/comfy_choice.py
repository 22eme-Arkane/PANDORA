"""ui/comfy_choice.py — Le choix « ComfyUI » des menus de moteurs.

Composant NEUTRE (ni Cinéma ni Live), comme ui/comfy_row.py.

Demande Matthieu (22/10/2026) : « pour le moment, on a une très longue liste
de ComfyUI ; j'aimerais avoir juste un réglage ComfyUI et pouvoir choisir le
moteur ». Les 101 gabarits d'image et les 24 gabarits d'édition vidéo
occupaient chacun une ligne de chaque menu de moteurs. Désormais :

  · `attach_comfy(menu, genre)` remplace toutes les entrées « comfy:… » (ou
    « comfy_edit:… ») d'un menu par UNE entrée « ComfyUI · <gabarit> », dont
    la donnée EST la clé du gabarit choisi — le code qui lit `currentData()`,
    enregistre ou génère ne change pas. Juste dessous, une ligne « Gabarit »
    (rangée par familles) + « Calcul », visible quand ComfyUI est choisi ;
  · « Calcul » — Ce PC (le ComfyUI local, comme avant) ou Mes machines ·
    AIODOS (core/aiodos, core/comfy_aiodos). UN réglage pour tout PANDORA
    (clé `comfy_compute`) : chaque menu « Calcul » le montre et le change, et
    tous se suivent (`hub`) ;
  · `ensure_comfy_ready(parent)` — ce qu'il faut vérifier avant de lancer un
    gabarit, selon ce réglage (remplace « ComfyUI de ce PC vivant ? » des
    onglets).
"""
from __future__ import annotations

import re

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QBoxLayout, QComboBox, QFormLayout, QHBoxLayout, QLabel, QLayout, QMessageBox, QWidget,
)

from core.i18n import translate
from ui.styles import CP

#: (libellé, valeur de `comfy_compute`). « Réseau public » (27/10/2026) : les
#: lieux cochés dans l'onglet AIODOS, réseau public compris — le choix par défaut
#: quand il y est coché (core/aiodos.compute_mode).
COMPUTE_CHOICES = (("Ce PC", "local"), ("Mes machines · AIODOS", "aiodos"),
                   ("Réseau public · AIODOS", "aiodos_public"))
#: Relecture du 28/10/2026 : AIODOS ne fait calculer les gabarits ComfyUI que par
#: ce PC et mes machines (il laisse de côté les autres cercles, et le dit dans
#: `where_effective`). Tant qu'il n'a pas pris le réseau public pour un travail
#: (core/aiodos.public_comfy_served), le choix le dit, dans la liste ; fermé, le
#: menu montre le libellé court.
PUBLIC_NOT_YET = "pas encore pour ComfyUI : calcul sur vos machines"
_SHORT_ROLE = 0x0100 + 7          # Qt.ItemDataRole.UserRole + 7 : le libellé court

#: Genre de menu → préfixe des clés de ses gabarits.
KINDS = {"image": "comfy:", "video_edit": "comfy_edit:"}
#: Le dernier gabarit choisi, par genre (repris à l'ouverture des menus).
LAST_KEYS = {"image": "comfy_last_image_template", "video_edit": "comfy_last_edit_template"}
#: Familles de gabarits vidéo (core/comfy_catalog « kind »), dans l'ordre affiché.
_VIDEO_GROUPS = (("edit", "Édition"), ("inpaint", "Inpainting"), ("upscale", "Agrandissement"),
                 ("character", "Personnage / mouvement"), ("interpolation", "Interpolation"),
                 ("other", "Outils"))


class _Hub(QObject):
    """Prévient tous les menus « Calcul » quand le réglage change."""
    compute_changed = pyqtSignal(str)


hub = _Hub()


def combo_style() -> str:
    return (
        f"QComboBox{{background:{CP['bg2']};border:1px solid {CP['border']};"
        f"border-radius:6px;color:{CP['text_primary']};font-size:11px;padding:0 8px;}}"
        f"QComboBox::drop-down{{border:none;width:20px;}}"
        f"QComboBox QAbstractItemView{{background:{CP['bg3']};"
        f"border:1px solid {CP['border_bright']};color:{CP['text_primary']};"
        f"selection-background-color:{CP['accent_dim']};}}")


class ComputeCombo(QComboBox):
    """« Calcul : Ce PC / Mes machines · AIODOS » — enregistré à chaque choix."""

    def __init__(self, parent=None, height: int = 30):
        super().__init__(parent)
        self.setFixedHeight(height)
        self.setStyleSheet(combo_style())
        self.setToolTip(translate(
            "Où se calcule le moteur IA : sur ce PC, réparti entre vos machines par "
            "AIODOS, ou sur le réseau public d'AIODOS (onglet AIODOS). Une image de "
            "référence ou un clip ne quitte jamais ce PC et vos machines."))
        # Fermé, le menu garde la largeur des libellés courts (paintEvent) ; la
        # liste dépliée s'élargit pour la mention du réseau public (style Fusion).
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(max(len(translate(l)) for l, _v in COMPUTE_CHOICES))
        for label, value in COMPUTE_CHOICES:
            self.addItem(translate(label), value)
            self.setItemData(self.count() - 1, translate(label), _SHORT_ROLE)
        self.sync()
        self.currentIndexChanged.connect(self._on_changed)
        hub.compute_changed.connect(self._on_hub)

    def _label_public(self):
        """« Réseau public · AIODOS — pas encore pour ComfyUI : calcul sur vos
        machines » tant qu'AIODOS ne l'a pas pris pour un gabarit."""
        from core import aiodos
        i = self.findData("aiodos_public")
        if i < 0:
            return
        short = translate("Réseau public · AIODOS")
        if aiodos.public_comfy_served():
            self.setItemText(i, short)
            self.setItemData(i, None, Qt.ItemDataRole.ToolTipRole)
        else:
            self.setItemText(i, f"{short} — {translate(PUBLIC_NOT_YET)}")
            self.setItemData(i, translate(
                "AIODOS ne fait pas encore calculer les gabarits ComfyUI par le réseau "
                "public : il les calcule sur ce PC et vos machines, et le dit après l'envoi."),
                Qt.ItemDataRole.ToolTipRole)

    def paintEvent(self, _event):
        """Le menu fermé montre le libellé court (« Réseau public · AIODOS »)."""
        from PyQt6.QtWidgets import QStyle, QStyleOptionComboBox, QStylePainter
        painter = QStylePainter(self)
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        short = self.itemData(self.currentIndex(), _SHORT_ROLE) if self.currentIndex() >= 0 else None
        if short:
            opt.currentText = str(short)
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, opt)
        painter.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, opt)

    def sync(self):
        from core import aiodos
        self._label_public()
        i = self.findData(aiodos.compute_mode())
        self.blockSignals(True)
        self.setCurrentIndex(i if i >= 0 else 0)
        self.blockSignals(False)

    def _on_hub(self, _mode: str):
        try:
            self.sync()
        except (RuntimeError, AttributeError):            # objet C++ détruit : plus rien à suivre
            pass

    def _on_changed(self, _i: int):
        mode = self.currentData() or "local"
        try:
            from core import aiodos
            aiodos.set_compute_mode(mode)
        except Exception:
            return
        hub.compute_changed.emit(mode)


# ── Une entrée « ComfyUI » + sa ligne Gabarit / Calcul ───────────────────────

def _catalog(kind: str) -> dict:
    """{nom du gabarit: entrée du cache} (core/comfy_catalog) — {} sans cache."""
    try:
        from core import comfy_catalog as _cc
        entries = _cc.load_cached() if kind == "image" else _cc.load_cached_video()
    except Exception:
        entries = []
    return {str(e.get("name")): e for e in entries if isinstance(e, dict) and e.get("name")}


def _title(label: str, entry: dict | None, key: str) -> str:
    if entry and entry.get("title"):
        return str(entry["title"])
    parts = [p.strip() for p in str(label or "").split("·")]
    return parts[1] if len(parts) > 1 and parts[0] == "ComfyUI" and parts[1] else (label or key)


def _group(kind: str, entry: dict | None, label: str) -> str:
    if kind == "image":
        edit = bool(entry.get("edit")) if entry else ("édition" in str(label or ""))
        return "Édition d'image (références)" if edit else "Texte → image"
    found = dict(_VIDEO_GROUPS).get((entry or {}).get("kind") or "other")
    return found or "Outils"


#: Familles de modèles reconnues dans le nom ou le titre d'un gabarit (le premier
#: motif qui correspond gagne) ; sinon le premier mot du titre (« Capybara »…).
_FAMILIES = (
    (r"flux\.?2|flux2", "Flux.2"),
    (r"krea[-_ ]?2", "Krea-2"),
    (r"flux|kontext", "Flux.1"),
    (r"qwen", "Qwen-Image"),
    (r"hidream", "HiDream"),
    (r"z[-_ ]?image", "Z-Image"),
    (r"chroma", "Chroma"),
    (r"mage[-_ ]?flow", "Mage-Flow"),
    (r"sd3", "SD 3.5"),
    (r"sdxl", "SDXL"),
)


#: Classement des familles, de la plus performante sur le marché à la moins
#: performante (Matthieu 27/10/2026 : « du plus performant sur le marché
#: actuellement au moins performant ») — d'après les classements publics des
#: modèles ouverts (arènes texte→image et édition) connus à ce jour. Une famille
#: absente de la liste vient après, rangée par taille ; SDXL ferme la marche.
_MARKET_RANK = ("Flux.2", "Qwen-Image", "Ideogram", "Z-Image", "HiDream", "Krea-2",
                "Flux.1", "LongCat", "Chroma", "Ernie", "Kandinsky", "OmniGen2",
                "SD 3.5")
_LAST = ("Anima", "NetaYume", "NewBie", "PixelDiT", "SDXL")


def market_rank(fam: str) -> int:
    if fam in _MARKET_RANK:
        return _MARKET_RANK.index(fam)
    if fam in _LAST:
        return 1000 + _LAST.index(fam)
    return len(_MARKET_RANK)


def family(entry: dict | None, label: str, key: str) -> str:
    """La famille de modèle d'un gabarit : « Z-Image » pour ses quatre variantes."""
    text = " ".join(str(x) for x in ((entry or {}).get("name"), (entry or {}).get("title"),
                                     label, key) if x).lower()
    for pattern, name in _FAMILIES:
        if re.search(pattern, text):
            return name
    title = _title(label, entry, key).split(":")[0].strip()
    return title.split()[0] if title else key


def _size(entry: dict | None) -> int:
    try:
        return int((entry or {}).get("size") or 0)
    except (TypeError, ValueError):
        return 0


def _template_text(label: str, entry: dict | None, key: str) -> str:
    bits = [_title(label, entry, key)]
    if entry:
        try:
            from core.comfy_catalog import gb
            size = int(entry.get("size") or 0)
            if size:
                bits.append(gb(size))
        except Exception:
            pass
        loads = int(entry.get("loads") or 0)
        if loads:
            bits.append(translate("{n} réf.").format(n=loads))
    return "  ·  ".join(bits)


def fill_templates(box: QComboBox, kind: str, items: list) -> dict:
    """Remplit un menu de moteurs IA (gabarits ComfyUI). Demande Matthieu
    (27/10/2026) : « trier en fonction des modèles, les grouper — un trait entre
    les familles — et les ranger par puissance, du plus puissant au moins
    puissant ». Sous chaque en-tête non sélectionnable (« ── Texte → image (49)
    ── »…), les familles de modèles (Flux.2, Qwen-Image, Z-Image…), chacune sous
    son titre et séparée par un trait, de la plus performante sur le marché à la
    moins performante (`_MARKET_RANK`), et dans chaque famille ses variantes de la
    plus lourde à la plus légère.
    `items` : [(clé, libellé du catalogue)]. Rend {clé: titre}."""
    prefix = KINDS[kind]
    cat = _catalog(kind)
    groups: dict = {}
    titles = {}
    for key, label in items:
        entry = cat.get(str(key)[len(prefix):])
        title = _title(label, entry, key)
        titles[key] = title
        fams = groups.setdefault(_group(kind, entry, label), {})
        fams.setdefault(family(entry, label, key), []).append(
            (_size(entry), title.lower(), key, _template_text(label, entry, key)))
    order = (["Texte → image", "Édition d'image (références)"] if kind == "image"
             else [g for _k, g in _VIDEO_GROUPS])
    order += [g for g in groups if g not in order]
    for name in order:
        fams = groups.get(name)
        if not fams:
            continue
        count = sum(len(rows) for rows in fams.values())
        box.addItem(f"── {translate(name)} ({count}) ──", None)
        head = box.model().item(box.count() - 1)
        if head is not None:
            head.setEnabled(False)
        ranked = sorted(fams.items(), key=lambda kv: (
            market_rank(kv[0]), -max(r[0] for r in kv[1]), kv[0].lower()))
        for n, (fam, rows) in enumerate(ranked):
            if n:
                box.insertSeparator(box.count())
            # Titre de famille (non sélectionnable) : la séparation se lit d'un
            # coup d'œil (« une plus grande séparation », 27/10/2026).
            box.addItem(f"▸  {fam}", None)
            title_item = box.model().item(box.count() - 1)
            if title_item is not None:
                title_item.setEnabled(False)
                font = title_item.font()
                font.setBold(True)
                title_item.setFont(font)
            for _size_b, _t, key, text in sorted(rows, key=lambda r: (-r[0], r[1])):
                box.addItem(text, key)
    return titles


def template_combo(kind: str, items: list, chosen: str = "") -> QComboBox:
    """Un menu « Gabarit » seul (fenêtre de choix multiple du Studio Images)."""
    box = QComboBox()
    box.setFixedHeight(26)
    box.setStyleSheet(combo_style())
    box.setMaxVisibleItems(22)
    box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    box.setMinimumContentsLength(18)
    fill_templates(box, kind, items)
    keys = [box.itemData(i) for i in range(box.count()) if box.itemData(i)]
    want = chosen if chosen in keys else (_remembered(kind) if _remembered(kind) in keys
                                          else (keys[0] if keys else ""))
    i = box.findData(want)
    if i >= 0:
        box.setCurrentIndex(i)
    return box


def _remembered(kind: str) -> str:
    try:
        from core.config import load_config
        return str(load_config().get(LAST_KEYS[kind]) or "")
    except Exception:
        return ""


def _remember(kind: str, key: str) -> None:
    """save_config REMPLACE tout le fichier : on repart de la config complète."""
    try:
        from core.config import load_config, save_config
        cfg = load_config()
        if cfg.get(LAST_KEYS[kind]) != key:
            cfg[LAST_KEYS[kind]] = key
            save_config(cfg)
    except Exception:
        pass


class ComfyChoice(QObject):
    """L'entrée « ComfyUI » d'un menu de moteurs et sa ligne Gabarit / Calcul.

    `row` est à placer sous le menu (attach_comfy le fait). Choisir un gabarit
    réécrit la donnée de l'entrée et, si ComfyUI est le moteur choisi, prévient
    la page : `on_template(clé)` si elle en donne un, sinon le signal
    currentIndexChanged du menu — ses gestionnaires relisent currentData()."""

    template_changed = pyqtSignal(str)

    def __init__(self, combo: QComboBox, kind: str, items: list, chosen: str, on_template=None,
                 label_width: int | None = None):
        super().__init__(combo)
        self.combo = combo
        self.kind = kind
        self.prefix = KINDS[kind]
        self._on_template = on_template
        self._texts = {}
        #: Les gabarits dans l'ordre où le menu les listait (celui du catalogue).
        self.original_keys = [k for k, _l in items]

        self.row = QWidget()
        self.row.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(self.row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lbl_style = f"color:{CP['text_dim']};font-size:11px;background:transparent;"
        # « Moteur IA » (Matthieu 27/10/2026 : « le nom gabarit ne va pas »).
        lbl = QLabel(translate("Moteur IA"))
        lbl.setStyleSheet(lbl_style)
        if label_width:
            lbl.setFixedWidth(label_width)      # aligné sur la colonne des libellés
        lay.addWidget(lbl)
        self.templates = QComboBox()
        self.templates.setFixedHeight(28)
        self.templates.setStyleSheet(combo_style())
        self.templates.setMaxVisibleItems(22)
        self.templates.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.templates.setMinimumContentsLength(18)
        self.templates.setToolTip(translate(
            "Le moteur IA (gabarit ComfyUI) qui calcule l'image ou la vidéo (0 $), rangé "
            "par famille de modèles, du plus puissant au plus léger. Les modèles qui "
            "manquent se téléchargent depuis Paramètres → Modules externes → ComfyUI."))
        self._fill(items)
        lay.addWidget(self.templates, 1)
        lbl2 = QLabel(translate("Calcul"))
        lbl2.setStyleSheet(lbl_style)
        lay.addWidget(lbl2)
        self.compute = ComputeCombo(height=28)
        self.compute.setMinimumWidth(190)
        lay.addWidget(self.compute)

        i = self.templates.findData(chosen)
        self.templates.setCurrentIndex(i if i >= 0 else self._first_template())
        self._apply_item(self.templates.currentData() or chosen)
        self.templates.currentIndexChanged.connect(self._on_template_index)
        combo.currentIndexChanged.connect(self._sync_visibility)
        self._sync_visibility()

    # ── Contenu ─────────────────────────────────────────────────────────────

    def _fill(self, items: list):
        self._texts = fill_templates(self.templates, self.kind, items)

    def _first_template(self) -> int:
        return next((i for i in range(self.templates.count()) if self.templates.itemData(i)), 0)

    def keys(self) -> list:
        return [self.templates.itemData(i) for i in range(self.templates.count())
                if self.templates.itemData(i)]

    # ── État ────────────────────────────────────────────────────────────────

    def item_index(self) -> int:
        """L'index de l'entrée « ComfyUI » dans le menu (−1 si elle a disparu)."""
        for i in range(self.combo.count()):
            if str(self.combo.itemData(i) or "").startswith(self.prefix):
                return i
        return -1

    def is_selected(self) -> bool:
        return str(self.combo.currentData() or "").startswith(self.prefix)

    def current_key(self) -> str:
        return str(self.templates.currentData() or "")

    def select(self, key: str) -> bool:
        """Choisit ce gabarit ET ComfyUI dans le menu ; faux si inconnu ici."""
        i = self.templates.findData(key)
        if i < 0 or self.item_index() < 0:
            return False
        if self.templates.currentIndex() != i:
            self.templates.setCurrentIndex(i)
        self.combo.setCurrentIndex(self.item_index())
        return True

    def _item_text(self, key: str) -> str:
        price = "$0" if self.kind == "image" else "0 $"
        return f"ComfyUI · {self._texts.get(key) or key[len(self.prefix):]}  ·  {price}"

    def _apply_item(self, key: str):
        i = self.item_index()
        if i >= 0 and key:
            self.combo.setItemData(i, key)
            self.combo.setItemText(i, self._item_text(key))

    def _on_template_index(self, _i: int):
        key = self.current_key()
        if not key:
            return
        try:
            self._apply_item(key)
            _remember(self.kind, key)
            self.template_changed.emit(key)
            if self.is_selected():
                if self._on_template is not None:
                    self._on_template(key)
                else:
                    self.combo.currentIndexChanged.emit(self.combo.currentIndex())
        except (RuntimeError, AttributeError):            # menu détruit
            pass

    def _sync_visibility(self, *_a):
        try:
            self.row.setVisible(self.is_selected())
        except (RuntimeError, AttributeError):
            pass


def _find(layout: QLayout, target):
    """(layout qui contient directement `target`, index) — en descendant."""
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item is None:
            continue
        if item.widget() is target or item.layout() is target:
            return layout, i
        sub = item.layout()
        if sub is not None:
            found = _find(sub, target)
            if found:
                return found
    return None


def _insert_after(layout, anchor, widget) -> bool:
    """Range `widget` juste après `anchor` (widget ou layout) dans `layout` :
    QBoxLayout, QFormLayout, ou une section repliable à `add_widget`."""
    if isinstance(layout, QFormLayout):
        if isinstance(anchor, QWidget):
            r, _role = layout.getWidgetPosition(anchor)
        else:
            r, _role = layout.getLayoutPosition(anchor)
        if r >= 0:
            layout.insertRow(r + 1, widget)
        else:
            layout.addRow(widget)
        return True
    if isinstance(layout, QBoxLayout):
        found = _find(layout, anchor)
        if found and found[0] is layout:
            layout.insertWidget(found[1] + 1, widget)
        else:
            layout.addWidget(widget)
        return True
    if not isinstance(layout, QLayout) and hasattr(layout, "add_widget"):
        layout.add_widget(widget)
        return True
    return False


def _auto_place(combo: QComboBox, widget: QWidget) -> bool:
    """Sous le menu : dans sa colonne s'il est dans une colonne, sinon sous la
    rangée horizontale qui le porte."""
    parent = combo.parentWidget()
    root = parent.layout() if parent is not None else None
    if root is None:
        return False
    found = _find(root, combo)
    if not found:
        return False
    holder, index = found
    if isinstance(holder, QBoxLayout) and holder.direction() in (
            QBoxLayout.Direction.TopToBottom, QBoxLayout.Direction.BottomToTop):
        holder.insertWidget(index + 1, widget)
        return True
    outer = _find(root, holder) if holder is not root else None
    if outer and isinstance(outer[0], (QBoxLayout, QFormLayout)):
        return _insert_after(outer[0], holder, widget)
    if isinstance(holder, QBoxLayout):
        holder.insertWidget(index + 1, widget)
        return True
    return False


def attach_comfy(combo: QComboBox, kind: str = "image", layout=None, after=None,
                 on_template=None) -> ComfyChoice | None:
    """Une seule entrée « ComfyUI » dans `combo` à la place de ses gabarits, et
    la ligne Gabarit / Calcul rangée après `after` dans `layout` (sinon sous le
    menu, trouvée seule). À appeler une fois le menu rempli ET son choix
    restauré : le gabarit déjà choisi est gardé, sinon le dernier utilisé.
    Rend None s'il n'y a aucun gabarit (ComfyUI jamais vu, mapping façade…)."""
    prefix = KINDS[kind]
    found = [(i, str(combo.itemData(i)), combo.itemText(i)) for i in range(combo.count())
             if str(combo.itemData(i) or "").startswith(prefix)]
    if not found:
        return None
    current = str(combo.currentData() or "")
    keys = [k for _i, k, _t in found]
    last = _remembered(kind)
    chosen = current if current in keys else (last if last in keys else keys[0])
    first = found[0][0]
    combo.blockSignals(True)
    try:
        for i, _k, _t in reversed(found):
            combo.removeItem(i)
        combo.insertItem(first, "ComfyUI", chosen)
        if current in keys:
            combo.setCurrentIndex(first)
    finally:
        combo.blockSignals(False)
    # Rangée « Libellé fixe | menu » : « Gabarit » prend la même largeur.
    width = None
    if isinstance(after, QBoxLayout) and after.count():
        first = after.itemAt(0).widget()
        if isinstance(first, QLabel) and 0 < first.minimumWidth() == first.maximumWidth():
            width = first.minimumWidth()
    choice = ComfyChoice(combo, kind, [(k, t) for _i, k, t in found], chosen, on_template,
                         label_width=width)
    combo._comfy_choice = choice
    if layout is not None:
        _insert_after(layout, after if after is not None else combo, choice.row)
    else:
        _auto_place(combo, choice.row)
    choice._sync_visibility()
    return choice


def comfy_choice_of(combo) -> ComfyChoice | None:
    return getattr(combo, "_comfy_choice", None)


def select_key(combo, key) -> bool:
    """Restaurer un moteur enregistré : un gabarit ComfyUI se choisit dans la
    ligne Gabarit (findData ne le trouverait pas : une seule entrée le porte)."""
    choice = comfy_choice_of(combo)
    return bool(choice is not None and str(key or "").startswith(choice.prefix)
                and choice.select(str(key)))


def ensure_comfy_ready(parent) -> tuple[bool, str]:
    """Avant de lancer un gabarit ComfyUI. Rend (prêt ?, raison).

    « Ce PC » : ComfyUI de ce PC vivant, sinon lancé et attendu
    (ui/external_autostart) — comme avant. « Mes machines · AIODOS » : AIODOS
    prêt (sinon la raison s'affiche), et de quoi PRÉPARER le gabarit — le
    ComfyUI de ce PC ou la dernière copie de ses définitions."""
    from core import comfy as _cf
    from core import comfy_aiodos as _ca
    if _ca.enabled():
        from core import aiodos as _ad
        ok, why = _ad.ready_for_comfy()
        if not ok:
            QMessageBox.warning(parent, "AIODOS", why)
            return False, why
        if _cf.discover() or _ca.has_saved_definitions():
            return True, ""
    elif _cf.discover():
        return True, ""
    from ui.external_autostart import ensure_ready
    if ensure_ready("comfyui", parent):
        return True, ""
    return False, translate("ComfyUI injoignable : lancez ComfyUI Desktop, puis relancez.")


def compute_label() -> str:
    """« Ce PC », « Mes machines · AIODOS » ou « Réseau public · AIODOS »,
    traduit (le libellé court, pour les résumés)."""
    from core import aiodos
    mode = aiodos.compute_mode()
    return translate(next((l for l, v in COMPUTE_CHOICES if v == mode), COMPUTE_CHOICES[0][0]))
