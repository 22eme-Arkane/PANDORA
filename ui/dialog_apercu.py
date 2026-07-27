"""Modal dialog — Mood storyboard : voir, naviguer, générer des variations."""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QProgressBar, QSizePolicy, QFrame, QTextEdit,
    QComboBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from core.i18n import translate
from PyQt6.QtGui import QPixmap
from ui.styles import CP, PANDORA_STYLESHEET
import core.storyboard as sb_api


def _btn(text: str, accent: bool = False, danger: bool = False) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(36)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if accent:
        b.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:8px;font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};}}"
        )
    elif danger:
        b.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['red']};"
            f"border:1px solid {CP['red']};border-radius:8px;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.12);}}"
        )
    else:
        b.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};border-color:{CP['bg3']};}}"
        )
    return b


# Le choix du MOTEUR se fait désormais DANS la fenêtre Mood (combo au-dessus du
# prompt) : le prompt affiché est écrit dans la grammaire du moteur sélectionné, donc
# le moteur doit être connu AVANT de générer, pas au moment du clic. L'ancienne
# fenêtre intermédiaire `choose_mood_engine` a été retirée (demande Matthieu
# 2026-07-25).


class MoodDialog(QDialog):
    apercu_changed = pyqtSignal(str, str)   # shot_id, active_image_path

    def __init__(self, parent, shot: dict):
        super().__init__(parent)
        self._shot        = shot
        self._paths: list[str] = []
        self._active_idx  = 0
        self._current_idx = 0
        self._worker      = None
        self._pulse_timer = QTimer(self)
        self._pulse_val   = 0
        self._pulse_dir   = 1
        # Le prompt a-t-il été retouché à la main ? Si oui, changer de moteur
        # ADAPTE le texte de l'utilisateur au lieu de l'écraser.
        self._prompt_dirty  = False
        self._prompt_quiet  = False   # garde anti-boucle sur setPlainText()

        n = shot.get("number", "?")
        title_text = (shot.get("scene_title") or "")[:60]
        self.setWindowTitle(f"Mood — Plan {n}")
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")
        from ui.widgets import fit_dialog_to_screen
        fit_dialog_to_screen(self, 0.70, 0.92, 760, 580)
        self.setModal(True)

        self._load()
        self._build_ui(n, title_text)
        self._refresh()

        from core.i18n import retranslate_widget
        retranslate_widget(self)

    # ── Data ──────────────────────────────────────────────────────────────────

    def _load(self):
        data = sb_api.load_apercus(self._shot["id"])
        self._paths = [p for p in data.get("paths", []) if os.path.isfile(p)]
        self._active_idx = min(
            data.get("active_idx", 0), max(0, len(self._paths) - 1)
        )
        self._current_idx = self._active_idx

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self, plan_num, title_text: str):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        # ── Titre ─────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        lbl_title = QLabel(
            f"Plan {plan_num}  ·  {title_text}" if title_text else f"Plan {plan_num}"
        )
        lbl_title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:14px;font-weight:700;background:transparent;"
        )
        hdr.addWidget(lbl_title, 1)
        btn_close = _btn("Fermer")
        btn_close.clicked.connect(self.accept)
        hdr.addWidget(btn_close)
        root.addLayout(hdr)

        # ── Bandeau description (déroulant) ───────────────────────────────────
        desc_frame = QFrame()
        desc_frame.setStyleSheet(
            f"QFrame{{background:rgba(78,205,196,0.07);border:1px solid rgba(78,205,196,0.22);"
            f"border-radius:8px;}}"
        )
        desc_lay = QVBoxLayout(desc_frame)
        desc_lay.setContentsMargins(14, 8, 14, 8)
        desc_lay.setSpacing(4)

        desc_title = QPushButton("▶  Qu'est-ce qu'un Mood ?")
        desc_title.setCheckable(True)
        desc_title.setChecked(False)
        desc_title.setCursor(Qt.CursorShape.PointingHandCursor)
        desc_title.setStyleSheet(
            f"QPushButton{{color:{CP['accent']};font-size:11px;font-weight:700;"
            f"background:transparent;border:none;text-align:left;padding:0;}}"
            f"QPushButton:hover{{color:#6eded6;}}"
        )
        desc_lay.addWidget(desc_title)

        desc_body = QLabel(
            "Teste le prompt et l'ambiance du plan avant de lancer Seedance 2.0. "
            "L'image est générée à partir du prompt Seedance, de la valeur de plan, "
            "la focale, l'axe caméra, le mouvement, le lieu, l'heure et le style visuel du film. "
            "Ce n'est pas une pré-visualisation fidèle — c'est un outil pour valider "
            "l'atmosphère, l'éclairage et le prompt. Une fois validée, l'image active "
            "pourra être injectée comme référence dans Seedance 2.0."
        )
        desc_body.setWordWrap(True)
        desc_body.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;line-height:1.5;"
            f"background:transparent;border:none;"
        )
        desc_body.setVisible(False)
        desc_lay.addWidget(desc_body)

        def _toggle_desc(checked: bool):
            desc_body.setVisible(checked)
            desc_title.setText(
                "▼  Qu'est-ce qu'un Mood ?" if checked else "▶  Qu'est-ce qu'un Mood ?"
            )
        desc_title.toggled.connect(_toggle_desc)
        root.addWidget(desc_frame)

        # ── Zone prompt modifiable ─────────────────────────────────────────────
        prompt_hdr = QHBoxLayout()
        prompt_lbl = QLabel("Prompt")
        prompt_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;font-weight:600;"
            f"background:transparent;"
        )
        prompt_hdr.addWidget(prompt_lbl)

        # Moteur de génération — CHOISI ICI, avant de générer. Le prompt ci-dessous
        # est réécrit dans la grammaire du moteur sélectionné : un brief à champs
        # pour Nano Banana / GPT Image, une prose sans interdit pour Seedream (son
        # API n'a plus de prompt négatif), un objet JSON pour FLUX.2.
        prompt_hdr.addSpacing(14)
        _eng_lbl = QLabel("Moteur")
        _eng_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:11px;background:transparent;")
        prompt_hdr.addWidget(_eng_lbl)
        self._engine_combo = self._build_engine_combo()
        prompt_hdr.addWidget(self._engine_combo)

        # Définition — juste après le moteur, les deux réglages du RENDU côte à
        # côte. C'est ici que ça compte le plus : le Mood sert d'image de départ
        # à la génération vidéo, donc son ratio est celui qui décide si la façade
        # se superposera au bâtiment réel ou s'il faudra la recaler à la main.
        prompt_hdr.addSpacing(10)
        _res_lbl = QLabel("Définition")
        _res_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:11px;background:transparent;")
        prompt_hdr.addWidget(_res_lbl)
        from ui.widgets import ResolutionCombo
        self._res_combo = ResolutionCombo(compact=True)
        prompt_hdr.addWidget(self._res_combo)

        self._grammar_lbl = QLabel("")
        self._grammar_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        prompt_hdr.addWidget(self._grammar_lbl)

        prompt_hdr.addStretch()
        btn_reset_prompt = QPushButton("↺  Réinitialiser")
        btn_reset_prompt.setFixedHeight(24)
        btn_reset_prompt.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset_prompt.setToolTip("Recharger le prompt depuis les données du plan")
        btn_reset_prompt.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:5px;"
            f"font-size:10px;padding:0 8px;}}"
            f"QPushButton:hover{{color:{CP['text_primary']};border-color:{CP['border_bright']};}}"
        )
        prompt_hdr.addWidget(btn_reset_prompt)
        root.addLayout(prompt_hdr)

        self._prompt_edit = QTextEdit()
        # Plus haut qu'avant : le brief à champs des moteurs Nano Banana / GPT
        # Image fait 6 à 8 lignes, et ce prompt est fait pour être RELU et corrigé
        # avant de générer, pas seulement deviné à travers une fente.
        self._prompt_edit.setFixedHeight(132)
        self._prompt_edit.setStyleSheet(
            f"QTextEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:11px;padding:6px;}}"
            f"QTextEdit:focus{{border-color:{CP['accent']};}}"
        )
        self._prompt_edit.textChanged.connect(self._on_prompt_typed)
        btn_reset_prompt.clicked.connect(self._reset_prompt)
        root.addWidget(self._prompt_edit)

        # Premier remplissage : prompt écrit pour le moteur sélectionné.
        self._reset_prompt()
        self._engine_combo.currentIndexChanged.connect(self._on_engine_changed)

        # ── Image principale ───────────────────────────────────────────────────
        self._img_lbl = QLabel()
        self._img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Minimum abaissé (760×427 → 640×360) pour compenser l'encart prompt plus
        # haut : la fenêtre doit rester ouvrable sur un écran de portable. L'aperçu
        # reste en Expanding et occupe tout l'espace disponible dès qu'il y en a.
        self._img_lbl.setMinimumSize(640, 360)
        self._img_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._img_lbl.setStyleSheet(
            f"background:{CP['bg0']};border:1px solid {CP['border']};border-radius:8px;"
        )
        root.addWidget(self._img_lbl, 1)

        # ── Bande de miniatures ────────────────────────────────────────────────
        self._thumb_scroll = QScrollArea()
        self._thumb_scroll.setFixedHeight(72)
        self._thumb_scroll.setWidgetResizable(True)
        self._thumb_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._thumb_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._thumb_scroll.setStyleSheet(
            "background:transparent;border:none;"
            "QScrollBar:horizontal{height:4px;}"
        )
        self._thumb_inner = QWidget()
        self._thumb_inner.setStyleSheet("background:transparent;")
        self._thumb_lay = QHBoxLayout(self._thumb_inner)
        self._thumb_lay.setContentsMargins(0, 4, 0, 4)
        self._thumb_lay.setSpacing(6)
        self._thumb_lay.addStretch()
        self._thumb_scroll.setWidget(self._thumb_inner)
        root.addWidget(self._thumb_scroll)

        # ── Navigation ────────────────────────────────────────────────────────
        nav = QHBoxLayout()
        self._btn_prev = _btn("◀")
        self._btn_prev.setFixedWidth(48)
        self._btn_prev.clicked.connect(lambda: self._nav(-1))
        nav.addWidget(self._btn_prev)

        self._count_lbl = QLabel("— / —")
        self._count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._count_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:11px;background:transparent;"
        )
        nav.addWidget(self._count_lbl, 1)

        self._btn_next = _btn("▶")
        self._btn_next.setFixedWidth(48)
        self._btn_next.clicked.connect(lambda: self._nav(1))
        nav.addWidget(self._btn_next)
        root.addLayout(nav)

        # ── Boutons d'action ──────────────────────────────────────────────────
        acts = QHBoxLayout()
        self._btn_activate = _btn("✓  Activer cette image", accent=True)
        self._btn_activate.clicked.connect(self._activate)
        acts.addWidget(self._btn_activate)

        self._btn_delete = _btn("🗑  Supprimer", danger=True)
        self._btn_delete.clicked.connect(self._delete)
        acts.addWidget(self._btn_delete)

        acts.addStretch()
        self._btn_import = _btn("⬆  Importer une image")
        self._btn_import.setToolTip(translate(
            "Utiliser une image à toi comme mood — choisie dans la\n"
            "bibliothèque ou sur le disque (copiée dans le plan)."))
        self._btn_import.clicked.connect(self._import_image)
        acts.addWidget(self._btn_import)
        self._btn_inspire = _btn("◎  Mood inspiré d'une image")
        self._btn_inspire.setToolTip(translate(
            "Choisis une image d'inspiration (bibliothèque ou disque) :\n"
            "son univers — palette, lumière, matières, style — est transposé\n"
            "sur la façade (mapping) ou réinterprété pour le plan.\n"
            "L'image n'est jamais collée telle quelle."))
        self._btn_inspire.clicked.connect(self._generate_from_image)
        acts.addWidget(self._btn_inspire)
        # ▦ Rogner à la façade — MAPPING uniquement (2026-07-26). Le moteur déborde
        # souvent de la silhouette du bâtiment : tout ce qui sort du cadre mappé est
        # perdu à la projection, et pollue les images de référence envoyées ensuite
        # à Seedance. Le bouton recale d'abord (un décalage de quelques pixels est
        # fréquent et corrigeable), puis noircit ce qui dépasse.
        self._btn_facade_crop = _btn("▦  Rogner à la façade")
        self._btn_facade_crop.setToolTip(translate(
            "Superpose ce mood à la façade de référence : recale un éventuel\n"
            "décalage, puis rend NOIR tout ce qui dépasse la silhouette.\n"
            "Si la géométrie a dérivé, PANDORA le dit — mieux vaut regénérer."))
        self._btn_facade_crop.clicked.connect(self._crop_to_facade)
        self._btn_facade_crop.setVisible(self._is_mapping())
        acts.addWidget(self._btn_facade_crop)

        self._btn_generate = _btn("✦  Générer une variation")
        self._btn_generate.clicked.connect(self._generate)
        acts.addWidget(self._btn_generate)
        root.addLayout(acts)

        # ── Barre de progression ───────────────────────────────────────────────
        progress_wrap = QWidget()
        progress_wrap.setFixedHeight(28)
        progress_wrap.setStyleSheet("background:transparent;")
        pw_lay = QVBoxLayout(progress_wrap)
        pw_lay.setContentsMargins(0, 4, 0, 0)
        pw_lay.setSpacing(3)

        self._progress = QProgressBar()
        self._progress.setFixedHeight(8)
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border:none;border-radius:4px;}}"
            f"QProgressBar::chunk{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {CP['accent']},stop:1 #6eded6);border-radius:4px;}}"
        )
        self._progress.hide()
        pw_lay.addWidget(self._progress)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;"
        )
        self._status_lbl.hide()
        pw_lay.addWidget(self._status_lbl)

        root.addWidget(progress_wrap)

        # Timer pour animation de la barre (pulsation 0→80→0)
        self._pulse_timer.timeout.connect(self._pulse_step)

    # ── Moteur de génération + prompt écrit pour lui ──────────────────────────

    def _build_engine_combo(self) -> QComboBox:
        """Liste des moteurs proposables ici. En séquence MAPPING FAÇADE elle se
        restreint aux moteurs qui savent éditer une image de référence (la
        géométrie du bâtiment doit être préservée)."""
        from api.apercu import mood_engine_choices, current_mood_is_mapping
        combo = QComboBox()
        combo.setFixedHeight(26)
        combo.setMinimumWidth(210)
        combo.setCursor(Qt.CursorShape.PointingHandCursor)
        combo.setStyleSheet(
            f"QComboBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:10px;padding:0 8px;}}"
            f"QComboBox::drop-down{{border:none;width:18px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};"
            f"border:1px solid {CP['border_bright']};color:{CP['text_primary']};"
            f"selection-background-color:{CP['accent_dim']};}}"
        )
        for _k, _lbl in mood_engine_choices(current_mood_is_mapping()):
            combo.addItem(_lbl, _k)
        # Reprend le dernier moteur utilisé, s'il est proposable dans ce contexte.
        _want = ""
        try:
            from core.config import load_config
            _want = (load_config().get("mood_engine") or "").strip()
        except Exception:
            pass
        _idx = combo.findData(_want) if _want else -1
        if _idx < 0:
            _idx = combo.findData("nb2")
        combo.setCurrentIndex(_idx if _idx >= 0 else 0)
        combo.setToolTip(translate(
            "Le prompt ci-dessous est réécrit dans la grammaire de ce moteur.\n"
            "Changer de moteur met le prompt à jour."))
        return combo

    def _current_engine(self) -> str:
        return self._engine_combo.currentData() or "nb2"

    def _set_prompt_text(self, text: str):
        """Écrit le prompt SANS le marquer comme retouché à la main."""
        self._prompt_quiet = True
        try:
            self._prompt_edit.setPlainText(text)
        finally:
            self._prompt_quiet = False

    def _refresh_grammar_label(self):
        from core.image_grammar import grammar_label
        self._grammar_lbl.setText("· " + translate(grammar_label(self._current_engine())))

    def _reset_prompt(self):
        """(Re)construit le prompt depuis les données du plan, pour le moteur choisi."""
        from api.apercu import build_mood_prompt
        import core.style as _style_mod
        self._set_prompt_text(build_mood_prompt(
            self._shot, _style_mod.get_image_suffix() or "", self._current_engine()))
        self._prompt_dirty = False
        self._refresh_grammar_label()

    def _on_prompt_typed(self):
        if not self._prompt_quiet:
            self._prompt_dirty = True

    def _on_engine_changed(self):
        """Changer de moteur change le prompt.

        Prompt jamais retouché → on le reconstruit entièrement. Prompt retouché à
        la main → on ADAPTE le texte de l'utilisateur (interdits convertis en
        positif si le moteur ne sait pas interdire, mots de qualité et termes
        vidéo retirés) plutôt que d'effacer son travail."""
        from core.image_grammar import adapt_prompt
        self._save_engine_pref()
        if not self._prompt_dirty:
            self._reset_prompt()
            return
        _txt, _ = adapt_prompt(self._prompt_edit.toPlainText().strip(),
                               self._current_engine())
        self._set_prompt_text(_txt)
        self._prompt_dirty = True   # le texte reste celui de l'utilisateur
        self._refresh_grammar_label()

    def _save_engine_pref(self):
        try:
            from core.config import load_config, save_config
            cfg = load_config()
            if (cfg.get("mood_engine") or "") != self._current_engine():
                cfg["mood_engine"] = self._current_engine()
                save_config(cfg)
        except Exception:
            pass

    # ── Pulsation de la barre ─────────────────────────────────────────────────

    def _pulse_step(self):
        self._pulse_val += self._pulse_dir * 3
        if self._pulse_val >= 80:
            self._pulse_val = 80
            self._pulse_dir = -1
        elif self._pulse_val <= 0:
            self._pulse_val = 0
            self._pulse_dir = 1
        self._progress.setValue(self._pulse_val)

    def _start_loading(self, msg: str = ""):
        self._progress.show()
        self._status_lbl.show()
        self._status_lbl.setText(translate(msg))
        self._pulse_val = 0
        self._pulse_dir = 1
        self._pulse_timer.start(25)

    def _stop_loading(self):
        self._pulse_timer.stop()
        self._progress.hide()
        self._status_lbl.hide()
        self._progress.setValue(0)

    # ── Affichage ─────────────────────────────────────────────────────────────

    def _refresh(self):
        has      = bool(self._paths)
        is_active = has and self._current_idx == self._active_idx

        # Image principale
        if has and 0 <= self._current_idx < len(self._paths):
            pix = QPixmap(self._paths[self._current_idx])
            if not pix.isNull():
                scaled = pix.scaled(
                    self._img_lbl.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._img_lbl.setPixmap(scaled)
                self._img_lbl.setText("")
            else:
                self._img_lbl.clear()
                self._img_lbl.setText("Image introuvable")
        else:
            self._img_lbl.clear()
            self._img_lbl.setText(
                "Aucun Mood disponible\n\nCliquez sur  ✦  Générer une variation  pour créer le premier"
            )
            self._img_lbl.setStyleSheet(
                f"background:{CP['bg0']};border:1px solid {CP['border']};border-radius:8px;"
                f"color:{CP['text_dim']};font-size:12px;"
            )

        # Navigation
        total = len(self._paths)
        self._count_lbl.setText(f"{self._current_idx + 1} / {total}" if has else "— / —")
        self._btn_prev.setEnabled(has and self._current_idx > 0)
        self._btn_next.setEnabled(has and self._current_idx < total - 1)
        self._btn_activate.setEnabled(has and not is_active)
        self._btn_activate.setText("✓  Image active" if is_active else "✓  Activer cette image")
        self._btn_delete.setEnabled(has)

        # Miniatures (rebuild)
        while self._thumb_lay.count() > 1:
            item = self._thumb_lay.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        for i, path in enumerate(self._paths):
            thumb = QLabel()
            thumb.setFixedSize(106, 62)
            thumb.setCursor(Qt.CursorShape.PointingHandCursor)
            pix = QPixmap(path).scaled(
                106, 62,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            pix = pix.copy((pix.width() - 106) // 2, (pix.height() - 62) // 2, 106, 62)
            thumb.setPixmap(pix)
            border = CP["accent"] if i == self._active_idx else (
                CP["border_bright"] if i == self._current_idx else CP["border"]
            )
            thumb.setStyleSheet(f"border:2px solid {border};border-radius:4px;")

            def _make_jump(idx):
                def _handler(_e):
                    self._current_idx = idx
                    self._refresh()
                return _handler
            thumb.mousePressEvent = _make_jump(i)
            self._thumb_lay.insertWidget(i, thumb)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._paths and 0 <= self._current_idx < len(self._paths):
            pix = QPixmap(self._paths[self._current_idx])
            if not pix.isNull():
                scaled = pix.scaled(
                    self._img_lbl.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._img_lbl.setPixmap(scaled)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _nav(self, delta: int):
        new_idx = self._current_idx + delta
        if 0 <= new_idx < len(self._paths):
            self._current_idx = new_idx
            self._refresh()

    # ── Rognage à la façade (Mapping) ─────────────────────────────────────────

    @staticmethod
    def _is_mapping() -> bool:
        """Séquence Mapping courante ? (le rognage n'a de sens que là)."""
        try:
            return sb_api.get_namespace() == "live_seq_mapping"
        except Exception:
            return False

    def _crop_to_facade(self):
        """Recale le mood sur la façade puis noircit ce qui dépasse.

        Trois issues : déjà aligné → on rogne ; décalage pur → on RECALE et on
        rogne (tous les moods finissent ainsi au même endroit, ce qui est le but :
        des images de référence sans défaut) ; déformation → on refuse de déplacer
        l'erreur et on propose de regénérer."""
        from PyQt6.QtWidgets import QMessageBox
        if not self._paths or not (0 <= self._current_idx < len(self._paths)):
            return
        src = self._paths[self._current_idx]

        from core.context import get_data_root
        from core.live_building import get_building_ref
        from core.live_mapping import (align_and_mask_image, ensure_facade_mask,
                                       measure_facade_alignment)
        ref = get_building_ref()
        if not ref or not os.path.isfile(ref):
            QMessageBox.information(
                self, translate("Façade absente"),
                translate("Ajoute d'abord la façade du bâtiment dans le Conducteur "
                          "(« Ajouter des références » → Référence bâtiment)."))
            return
        mask = ensure_facade_mask(ref, get_data_root())
        if not mask:
            # Message DIAGNOSTIQUE (2026-07-26) : « détoure-la d'abord » ne disait
            # ni ce qui avait été mesuré, ni où se trouve l'outil qui le fait. Les
            # deux causes se soignent différemment, il faut donc les distinguer.
            from core.live_mapping import (facade_mask_coverage,
                                           _MASK_MAX_COVER, _MASK_MIN_COVER)
            _cov = facade_mask_coverage(ref)
            if _cov < 0:
                _cause = translate("l'image est illisible.")
            elif _cov >= _MASK_MAX_COVER:
                _cause = translate(
                    "presque tout le cadre est éclairé — il n'y a pas de fond noir "
                    "autour du bâtiment, c'est encore une photo avec son décor.")
            else:
                _cause = translate(
                    "presque rien ne ressort du fond — l'image est trop sombre pour "
                    "qu'une silhouette s'en détache.")
            QMessageBox.warning(
                self, translate("Façade non isolée"),
                translate("Impossible de tirer un masque de la façade de référence.")
                + f"\n\n{_cause}\n\n"
                + translate("Mesuré : {pct} % du cadre éclairé (il en faut entre "
                            "{lo} et {hi} %).").format(
                    pct=("?" if _cov < 0 else int(_cov * 100)),
                    lo=int(_MASK_MIN_COVER * 100), hi=int(_MASK_MAX_COVER * 100))
                + "\n\n"
                + translate("Conducteur → « Ajouter des références » → Référence "
                            "bâtiment → bouton « ◐ Isoler (fond noir) »."))
            return

        m = measure_facade_alignment(src, mask)
        verdict = m.get("verdict", "unavailable")
        if verdict == "unavailable":
            QMessageBox.warning(self, translate("Mesure impossible"), translate(
                "Impossible de comparer ce mood à la façade (image illisible ou vide)."))
            return
        if verdict == "deformed":
            # On ne recale PAS : déplacer une géométrie déformée ne fait que
            # déplacer l'erreur. C'est la règle posée par Matthieu.
            QMessageBox.warning(
                self, translate("Géométrie déformée"),
                translate(
                    "Ce mood ne se superpose pas à la façade : la géométrie du "
                    "bâtiment a dérivé pendant la génération (recouvrement "
                    "{iou} %, {missing} % de la façade non couverte).\n\n"
                    "Un recalage ne ferait que déplacer l'erreur. Mieux vaut "
                    "REGÉNÉRER ce mood.").format(
                        iou=int(m["iou_aligned"] * 100), missing=int(m["missing"] * 100)))
            return

        dy, dx = m.get("shift", (0, 0))
        import hashlib
        _key = hashlib.md5(f"{src}|{os.path.getmtime(src)}|{mask}".encode()).hexdigest()[:12]
        out = os.path.join(get_data_root(), "mapping", "moods_rognes", f"{_key}.png")
        try:
            align_and_mask_image(src, mask, out, (dy, dx))
        except Exception as e:
            QMessageBox.warning(self, translate("Rognage impossible"), str(e))
            return

        # Le rognage AJOUTE une image et l'active : l'original reste dans la
        # galerie, on peut toujours y revenir.
        self._paths.insert(self._current_idx + 1, out)
        self._current_idx += 1
        self._active_idx = self._current_idx
        sb_api.save_apercus(self._shot["id"], self._paths, self._active_idx)
        self.apercu_changed.emit(self._shot["id"], out)
        self._refresh()

        _quoi = (translate("recalé de {dy}/{dx} px puis rogné").format(dy=dy, dx=dx)
                 if (dy or dx) else translate("rogné à la silhouette"))
        _extra = ""
        if m.get("overflow", 0) > 0:
            _extra = " " + translate("({pc} % de lumière hors façade supprimée)").format(
                pc=round(m["overflow"] * 100, 1))
        QMessageBox.information(
            self, translate("Mood aligné sur la façade"),
            translate("Mood {quoi}.{extra}\n\nL'original reste dans la galerie.")
            .format(quoi=_quoi, extra=_extra))

    def _activate(self):
        if not self._paths:
            return
        self._active_idx = self._current_idx
        sb_api.save_apercus(self._shot["id"], self._paths, self._active_idx)
        self.apercu_changed.emit(self._shot["id"], self._paths[self._active_idx])
        self._refresh()

    def _delete(self):
        if not self._paths or not (0 <= self._current_idx < len(self._paths)):
            return
        path = self._paths[self._current_idx]
        # Supprimer le fichier sur disque
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass
        self._paths.pop(self._current_idx)
        # Recalculer l'index actif
        if self._paths:
            self._active_idx = min(self._active_idx, len(self._paths) - 1)
            self._current_idx = min(self._current_idx, len(self._paths) - 1)
        else:
            self._active_idx  = 0
            self._current_idx = 0
        sb_api.save_apercus(self._shot["id"], self._paths, self._active_idx)
        active_path = self._paths[self._active_idx] if self._paths else ""
        self.apercu_changed.emit(self._shot["id"], active_path)
        self._refresh()

    def _disconnect_worker(self):
        if self._worker is None:
            return
        try:
            self._worker.progress.disconnect(self._on_progress)
            self._worker.finished.disconnect(self._on_generated)
            self._worker.failed.disconnect(self._on_failed)
        except Exception:
            pass

    def accept(self):
        self._disconnect_worker()
        super().accept()

    def reject(self):
        self._disconnect_worker()
        super().reject()

    def _import_image(self):
        """Importer un mood (bibliothèque ou disque) — copié dans le dossier du plan,
        au même titre qu'un mood généré : navigable, activable, supprimable."""
        from ui.dialog_image_library import ImageLibraryDialog
        paths = ImageLibraryDialog.pick(self)
        if not paths:
            return
        import shutil
        dest = sb_api.get_apercu_dir(self._shot["id"])
        os.makedirs(dest, exist_ok=True)
        added = 0
        for src in paths:
            if not (src and os.path.isfile(src)):
                continue
            base, ext = os.path.splitext(os.path.basename(src))
            dst = os.path.join(dest, f"import_{base}{ext}")
            i = 1
            while os.path.exists(dst):
                dst = os.path.join(dest, f"import_{base}_{i}{ext}")
                i += 1
            try:
                shutil.copy2(src, dst)
            except OSError:
                continue
            self._paths.append(dst)
            added += 1
        if not added:
            return
        self._current_idx = len(self._paths) - 1
        sb_api.save_apercus(self._shot["id"], self._paths, self._active_idx)
        self._status_lbl.setText(translate("Image(s) importée(s) — clique « Activer » pour en faire le mood du plan."))
        self._status_lbl.show()
        self._refresh()

    def _generate(self):
        # Le moteur est choisi DANS la fenêtre (combo au-dessus du prompt) : plus
        # de fenêtre intermédiaire, et le prompt affiché est déjà écrit pour lui.
        self._start_generation(engine=self._current_engine())

    def _generate_from_image(self):
        """Mood inspiré : l'image choisie sert de DA (transposée, jamais collée)."""
        from ui.dialog_image_library import ImageLibraryDialog
        paths = ImageLibraryDialog.pick(self)
        if not paths:
            return
        self._start_generation(inspiration_ref=paths[0], engine=self._current_engine())

    def _start_generation(self, inspiration_ref: str = "", engine: str = ""):
        from api.apercu import MoodGenerationWorker
        apercu_dir  = sb_api.get_apercu_dir(self._shot["id"])
        custom_prompt = self._prompt_edit.toPlainText().strip()
        self._disconnect_worker()
        # La définition part TOUJOURS, même sans moteur explicite : l'ancien
        # `options=None` quand `engine` était vide aurait fait retomber le Mood
        # sur le défaut de l'API et rendu le sélecteur inopérant une fois sur deux.
        _opts = {"resolution": self._res_combo.resolution_key()}
        if engine:
            _opts["engine"] = engine
        self._worker = MoodGenerationWorker(self._shot, apercu_dir,
                                            custom_prompt=custom_prompt,
                                            inspiration_ref=inspiration_ref,
                                            options=_opts)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_generated)
        self._worker.failed.connect(self._on_failed)
        self._btn_generate.setEnabled(False)
        self._btn_inspire.setEnabled(False)
        self._btn_activate.setEnabled(False)
        self._start_loading("Mood inspiré de l'image…" if inspiration_ref
                            else "Génération du Mood…")
        self._worker.start()

    def _on_progress(self, msg: str):
        self._status_lbl.setText(translate(msg))

    def _on_generated(self, path: str):
        self._stop_loading()
        self._btn_generate.setEnabled(True)
        self._btn_inspire.setEnabled(True)
        if path and os.path.isfile(path):
            self._paths.append(path)
            self._current_idx = len(self._paths) - 1
            sb_api.save_apercus(self._shot["id"], self._paths, self._active_idx)
        self._refresh()

    def _on_failed(self, error: str):
        self._stop_loading()
        self._status_lbl.setText(f"Erreur : {error[:120]}")
        self._status_lbl.show()
        self._btn_generate.setEnabled(True)
        self._btn_inspire.setEnabled(True)
        self._btn_activate.setEnabled(bool(self._paths) and self._current_idx != self._active_idx)
