"""Modal dialog — Mood storyboard : voir, naviguer, générer des variations."""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QProgressBar, QSizePolicy, QFrame, QTextEdit,
    QComboBox, QSpinBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QThread
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


class _MoodPromptWorker(QThread):
    """Compose le prompt final IMAGE du Mood. Repli déterministe garanti.

    `done` et jamais `finished` : `finished` masquerait le signal natif de
    QThread. Une seule chose est interdite — ne rien émettre : une branche muette
    laisserait la mention « composition… » affichée pour toujours.
    """

    done = pyqtSignal(str, bool, str, bool)   # (prompt, composé, raison, du_cache)

    def __init__(self, shot: dict, style: str, engine: str,
                 building_ref: str, is_mapping: bool, fresh: bool = False):
        super().__init__()
        self._shot   = shot or {}
        self._style  = style or ""
        self._engine = engine or ""
        self._bref   = building_ref or ""
        self._mapping = bool(is_mapping)
        self._fresh   = bool(fresh)

    def run(self):
        """Délègue à `api.apercu.compose_mood_prompt` — le MÊME chemin que le lot.

        Y compris son cache sur disque : refermer puis rouvrir la fenêtre ne doit
        pas repayer un aller-retour IA quand rien n'a changé dans le plan.
        """
        try:
            from api.apercu import compose_mood_prompt
            _p, _ok, _why, _cache = compose_mood_prompt(
                self._shot, self._style, self._engine, self._bref,
                is_mapping=self._mapping, force_fresh=self._fresh)
            self.done.emit(_p, _ok, _why, _cache)
        except Exception as exc:
            self.done.emit("", False, str(exc)[:200], False)


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
        # Composition IA du prompt final (2026-07-27). Le cache évite de repayer
        # un aller-retour quand on rouvre le même plan sans rien changer.
        self._compose_worker = None
        self._compose_cache: dict = {}
        self._compose_why    = ""
        self._compose_done   = False
        self._compose_from_cache = False
        # Posé par « Réinitialiser » : la PROCHAINE composition ignore le cache
        # (un refus mémorisé doit pouvoir être retenté). Consommé par
        # _start_compose, un seul envoi.
        self._compose_fresh  = False
        # Barre de chargement de la composition : pulsation MANUELLE, comme la
        # barre de génération — le mode indéterminé de Qt ne s'anime pas
        # toujours avec un chunk stylé. Timer dédié : celui de la génération
        # est arrêté par _stop_loading, qui ne doit pas geler cette barre-ci.
        self._composing          = False
        self._compose_pulse      = QTimer(self)
        self._compose_pulse.setInterval(25)
        self._compose_pulse.timeout.connect(self._compose_pulse_step)
        self._compose_pulse_val  = 0
        self._compose_pulse_dir  = 1
        self._compose_timer  = QTimer(self)
        self._compose_timer.setSingleShot(True)
        self._compose_timer.setInterval(250)
        self._compose_timer.timeout.connect(self._start_compose)

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

        # (Pas de sélecteur d'instant : le Mood rend l'état d'ARRIVÉE pour TOUS
        # les plans — décision Matthieu 2026-07-28, après essai d'un combo
        # auto/début/fin retiré le jour même : « c'est l'action même du plan
        # qui nous intéresse, pas le début, qui est la continuité du plan
        # précédent ». La doctrine vit dans api.apercu._build_mood_prompt_live.)

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

        prompt_hdr.addSpacing(10)
        _fmt_lbl = QLabel(translate("Format"))
        _fmt_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:11px;background:transparent;")
        prompt_hdr.addWidget(_fmt_lbl)
        from ui.widgets import RatioCombo
        self._ratio_combo = RatioCombo(compact=True, auto_hint="16:9")
        prompt_hdr.addWidget(self._ratio_combo)

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

        # Barre de chargement de la COMPOSITION — à la place du libellé
        # « composition du prompt… » : un texte gris ne se voit pas, une barre
        # qui pulse dit clairement qu'un aller-retour IA est en cours
        # (demande Matthieu 2026-07-28).
        self._compose_row = QWidget()
        _cl = QHBoxLayout(self._compose_row)
        _cl.setContentsMargins(0, 2, 0, 0)
        _cl.setSpacing(8)
        self._compose_bar = QProgressBar()
        self._compose_bar.setFixedHeight(6)
        self._compose_bar.setFixedWidth(180)
        self._compose_bar.setTextVisible(False)
        self._compose_bar.setRange(0, 100)
        self._compose_bar.setValue(0)
        self._compose_bar.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border:none;border-radius:3px;}}"
            f"QProgressBar::chunk{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {CP['accent']},stop:1 #6eded6);border-radius:3px;}}"
        )
        _cl.addWidget(self._compose_bar)
        _compose_lbl = QLabel(translate("composition du prompt par l'IA…"))
        _compose_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        _cl.addWidget(_compose_lbl)
        _cl.addStretch()
        self._compose_row.setVisible(False)
        root.addWidget(self._compose_row)

        # Ligne d'état de la composition — SOUS l'en-tête, pleine largeur.
        # Dans l'en-tête, la grammaire et surtout la RAISON d'un échec étaient
        # tronquées à quelques lettres (« ⚠ comp… ») : une erreur illisible ne
        # se corrige pas (constat Matthieu 2026-07-28).
        self._grammar_lbl = QLabel("")
        self._grammar_lbl.setWordWrap(True)
        self._grammar_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        root.addWidget(self._grammar_lbl)

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
        # « ▦ Rogner à la façade » RETIRÉ le 2026-07-27 sur demande de Matthieu :
        # le bouton ne rendait pas le service attendu. Le masquage lui-même reste
        # en place et automatique — `core.live_mapping.masked_keyframe` confine le
        # mood à la silhouette AVANT de l'envoyer comme image-clé de mapping. Ce
        # n'est donc pas la fonction qui disparaît, seulement son déclenchement
        # manuel.

        self._btn_generate = _btn("✦  Générer une variation")
        self._btn_generate.clicked.connect(self._generate)
        acts.addWidget(self._btn_generate)

        # Annuler — une génération peut durer et coûter. Le bouton n'apparaît que
        # PENDANT, à la place occupée par le regard : juste après « Générer ».
        self._btn_cancel_gen = _btn("✕  Annuler", danger=True)
        self._btn_cancel_gen.setToolTip(translate(
            "Arrête la génération en cours. Les variations déjà obtenues sont "
            "conservées."))
        self._btn_cancel_gen.clicked.connect(self._cancel_generation)
        self._btn_cancel_gen.setVisible(False)
        acts.addWidget(self._btn_cancel_gen)

        # ×N — plusieurs variations d'un coup. Chaque variation est un appel
        # facturé : le compteur reste donc à 1 par défaut, et le bouton dit
        # combien partent réellement plutôt que de laisser la surprise à la
        # facture.
        _x = QLabel("×")
        _x.setStyleSheet(
            f"color:{CP['text_dim']};font-size:12px;background:transparent;")
        acts.addWidget(_x)
        self._spin_variations = QSpinBox()
        self._spin_variations.setRange(1, 8)
        self._spin_variations.setValue(1)
        self._spin_variations.setFixedSize(52, 34)
        self._spin_variations.setToolTip(translate(
            "Nombre de variations à générer d'affilée. "
            "Chaque variation est une génération facturée."))
        self._spin_variations.setStyleSheet(
            f"QSpinBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:12px;"
            f"padding:0 4px;}}"
            f"QSpinBox::up-button, QSpinBox::down-button{{width:16px;}}")
        self._spin_variations.valueChanged.connect(self._sync_generate_label)
        acts.addWidget(self._spin_variations)
        self._sync_generate_label()
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

    def _refresh_grammar_label(self, status: str = ""):
        """Grammaire du moteur + verdict de la composition.

        Le verdict doit se LIRE : un repli silencieux passerait pour un bug de
        l'application, et c'est précisément ce qui a rendu le diagnostic si long
        du côté vidéo.
        """
        from core.image_grammar import grammar_label
        _txt = "· " + translate(grammar_label(self._current_engine()))
        if getattr(self, "_composing", False):
            # La barre de chargement dit déjà « en cours » : afficher en plus
            # l'ancien verdict (un ⚠ périmé, surtout) ferait croire que
            # l'erreur persiste pendant qu'on recompose.
            self._grammar_lbl.setText(_txt)
            self._grammar_lbl.setToolTip(_txt)
            return
        if status:
            _txt += "  ·  " + status
        elif self._prompt_dirty:
            _txt += "  ·  " + translate("prompt retouché à la main")
        elif self._compose_done:
            _txt += "  ·  " + (translate("♻ déjà composé") if self._compose_from_cache
                               else translate("✓ composé pour ce moteur"))
        elif self._compose_why:
            # La raison COMPLÈTE : la ligne d'état est en pleine largeur avec
            # retour à la ligne — une erreur tronquée à quelques lettres ne se
            # corrige pas (constat Matthieu 2026-07-28 : « ⚠ comp… »).
            _txt += "  ·  ⚠ " + self._compose_why[:240]
        self._grammar_lbl.setText(_txt)
        # Le texte intégral reste consultable au survol, verdict compris.
        self._grammar_lbl.setToolTip(
            _txt + (("\n\n" + self._compose_why) if self._compose_why else ""))

    def _reset_prompt(self):
        """(Re)construit le prompt depuis les données du plan, pour le moteur choisi."""
        from api.apercu import build_mood_prompt
        import core.style as _style_mod
        self._set_prompt_text(build_mood_prompt(
            self._shot, _style_mod.get_image_suffix() or "",
            self._current_engine()))
        self._prompt_dirty = False
        self._refresh_grammar_label()
        # Le texte déterministe s'affiche TOUT DE SUITE — l'encart n'est jamais
        # vide — puis la composition le remplace quand elle revient. FRAÎCHE :
        # « Réinitialiser » doit RETENTER la composition, pas resservir le
        # cache — un refus du contrôle y est mémorisé, et le resservir
        # réaffichait la même erreur à l'identique (constat Matthieu
        # 2026-07-28 : « le bouton Réinitialiser ne semble pas marcher »).
        self._compose_fresh = True
        self._schedule_compose()

    # ── Composition IA du prompt final image ─────────────────────────────────
    # (Pas de _compose_inputs ici : TOUT passe par le worker, qui délègue à
    # api.apercu.compose_mood_prompt — un seul chemin, un seul cache, partagé
    # avec le lot. Une construction locale de la fiche n'a plus d'appelant
    # depuis cette délégation, et en garder une inviterait à composer sur le
    # thread UI.)

    def _schedule_compose(self):
        """Programme la composition. Débounce : changer de moteur en cascade ne
        doit lancer qu'UN appel, pas un par cran du combo."""
        try:
            self._compose_timer.start()
        except Exception:
            pass

    def _start_compose(self):
        try:
            # L'utilisateur a repris la main : son texte prime, on ne l'écrase pas.
            if self._prompt_dirty:
                return
            try:
                import core.style as _sm
                _style = _sm.get_image_suffix() or ""
            except Exception:
                _style = ""
            _bref = ""
            if self._is_mapping():
                try:
                    from api.apercu import _resolve_building_ref
                    _bref = _resolve_building_ref()
                except Exception:
                    _bref = ""
            # Parquer le worker précédent AVANT de réassigner : un QThread qui
            # surcharge run() n'a pas de boucle d'événements, et le laisser au
            # ramasse-miettes pendant qu'il tourne fait planter l'application.
            if self._compose_worker is not None:
                try:
                    from core.worker import abandon_thread
                    abandon_thread(self._compose_worker)
                except Exception:
                    pass
                self._compose_worker = None

            # La barre remplace le libellé « composition du prompt… » : elle
            # pulse tant que l'aller-retour IA n'est pas revenu.
            self._composing = True
            self._compose_row.setVisible(True)
            self._compose_pulse_val = 0
            self._compose_pulse_dir = 1
            self._compose_pulse.start()
            self._refresh_grammar_label()
            _fresh = bool(getattr(self, "_compose_fresh", False))
            self._compose_fresh = False   # le drapeau ne vaut que pour UN envoi
            self._compose_worker = _MoodPromptWorker(
                self._shot, _style, self._current_engine(), _bref,
                self._is_mapping(), fresh=_fresh)
            self._compose_worker.done.connect(self._on_composed)
            self._compose_worker.start()
        except Exception:
            # Une exception non gérée dans un slot PyQt6 fait ABORT toute l'app.
            self._refresh_grammar_label()

    def _on_composed(self, prompt: str, composed: bool, why: str,
                     from_cache: bool = False):
        try:
            self._composing = False
            self._compose_pulse.stop()
            self._compose_row.setVisible(False)
            self._compose_why  = why or ""
            self._compose_done = bool(composed)
            self._compose_from_cache = bool(from_cache)
            if self._prompt_dirty:
                self._refresh_grammar_label()
                return
            if (prompt or "").strip():
                self._set_prompt_text(prompt.strip())
            self._refresh_grammar_label()
        except Exception:
            pass

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
        # Pas de composition ici : le texte appartient à l'utilisateur, on
        # l'ADAPTE au nouveau moteur sans le réécrire.

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

    def _compose_pulse_step(self):
        self._compose_pulse_val += self._compose_pulse_dir * 3
        if self._compose_pulse_val >= 80:
            self._compose_pulse_val = 80
            self._compose_pulse_dir = -1
        elif self._compose_pulse_val <= 0:
            self._compose_pulse_val = 0
            self._compose_pulse_dir = 1
        self._compose_bar.setValue(self._compose_pulse_val)

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
            # ACTIVE = SOULIGNÉE d'un trait vert néon ; SÉLECTIONNÉE = rectangle
            # néon (demande Matthieu 2026-07-28 : l'encadré de l'active se
            # confondait avec la sélection — impossible de savoir laquelle
            # partirait comme plaque du plan). Une vignette peut être les deux :
            # rectangle néon ET souligné vert.
            _cadre = CP["accent"] if i == self._current_idx else CP["border"]
            _style = f"border:2px solid {_cadre};border-radius:4px;"
            if i == self._active_idx:
                _style += f"border-bottom:4px solid {CP['green']};"
            thumb.setStyleSheet(_style)
            thumb.setToolTip(
                translate("Image active du plan") if i == self._active_idx
                else "")

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

    def _sync_generate_label(self, *_):
        """Le bouton dit ce qu'il va faire : « une » ou « N » variations."""
        try:
            n = self._spin_variations.value()
        except Exception:
            n = 1
        self._btn_generate.setText(
            translate("✦  Générer une variation") if n == 1
            else translate("✦  Générer") + f" {n} " + translate("variations"))

    def _disconnect_worker(self):
        if self._worker is None:
            return
        try:
            self._worker.progress.disconnect(self._on_progress)
            self._worker.finished.disconnect(self._on_generated)
            self._worker.multi_finished.disconnect(self._on_generated_multi)
            self._worker.failed.disconnect(self._on_failed)
        except Exception:
            pass

    def _park_compose_worker(self):
        """Un worker de composition qui survit au dialogue émettrait vers un
        objet détruit. JAMAIS terminate() : état Qt corrompu et segfault sur le
        worker suivant."""
        try:
            self._compose_timer.stop()
        except Exception:
            pass
        if getattr(self, "_compose_worker", None) is not None:
            try:
                from core.worker import abandon_thread
                abandon_thread(self._compose_worker)
            except Exception:
                pass
            self._compose_worker = None

    def accept(self):
        self._disconnect_worker()
        self._park_compose_worker()
        super().accept()

    def reject(self):
        self._disconnect_worker()
        self._park_compose_worker()
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

    def _cancel_generation(self):
        """Arrête la génération en cours SANS perdre ce qui est déjà obtenu.

        JAMAIS `QThread.terminate()` : l'état Qt/Python en ressort corrompu et le
        worker SUIVANT part en segfault. `abandon_thread` bloque les signaux,
        demande l'interruption et garde une référence anti-GC — la boucle des
        variations la teste entre deux tirages et sort proprement.

        Les variations déjà enregistrées restent : elles ont été écrites au fil
        de l'eau, elles sont valides, et les jeter parce qu'on interrompt la
        suite n'aurait aucun sens.
        """
        try:
            if self._worker is not None:
                self._disconnect_worker()
                try:
                    from core.worker import abandon_thread
                    abandon_thread(self._worker)
                except Exception:
                    pass
                self._worker = None
            self._stop_loading()
            self._status_lbl.setText(translate("Génération annulée."))
            self._status_lbl.show()
            self._restore_after_generation()
            # Ce qui a été produit avant l'arrêt doit apparaître.
            self._load()
            self._refresh()
        except Exception:
            self._restore_after_generation()

    def _restore_after_generation(self):
        """Rend la main : boutons réactivés, « Annuler » masqué."""
        try:
            self._btn_cancel_gen.setVisible(False)
            self._btn_generate.setEnabled(True)
            self._btn_inspire.setEnabled(True)
        except Exception:
            pass

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
        _opts = {"resolution": self._res_combo.resolution_key(),
                 "aspect_ratio": self._ratio_combo.ratio()}
        if engine:
            _opts["engine"] = engine
        self._worker = MoodGenerationWorker(self._shot, apercu_dir,
                                            custom_prompt=custom_prompt,
                                            inspiration_ref=inspiration_ref,
                                            options=_opts,
                                            variations=self._spin_variations.value())
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_generated)
        self._worker.multi_finished.connect(self._on_generated_multi)
        self._worker.failed.connect(self._on_failed)
        self._btn_cancel_gen.setVisible(True)
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
        self._restore_after_generation()
        if path and os.path.isfile(path):
            self._paths.append(path)
            self._current_idx = len(self._paths) - 1
            sb_api.save_apercus(self._shot["id"], self._paths, self._active_idx)
        self._refresh()

    def _on_generated_multi(self, paths: list):
        """Série de variations. On se place sur la PREMIÈRE des nouvelles : c'est
        celle qu'on vient de demander, et la navigation permet de parcourir les
        suivantes sans en manquer une."""
        self._stop_loading()
        self._restore_after_generation()
        _new = [p for p in (paths or []) if p and os.path.isfile(p)]
        if _new:
            _first = len(self._paths)
            self._paths.extend(_new)
            self._current_idx = _first
            sb_api.save_apercus(self._shot["id"], self._paths, self._active_idx)
        self._refresh()

    def _on_failed(self, error: str):
        self._stop_loading()
        self._status_lbl.setText(f"Erreur : {error[:120]}")
        self._status_lbl.show()
        self._btn_generate.setEnabled(True)
        self._btn_inspire.setEnabled(True)
        self._btn_activate.setEnabled(bool(self._paths) and self._current_idx != self._active_idx)
