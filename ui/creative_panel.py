"""
Panneau de contrôles créatifs — chips à bascule par module.

Usage :
    from ui.creative_panel import CreativeControlsPanel, CASTING_CONTROLS
    self._creative = CreativeControlsPanel(CASTING_CONTROLS)
    lay.addWidget(self._creative)

    # À la génération :
    suffix = self._creative.get_suffix()   # English string, comma-separated
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QSlider,
)
from PyQt6.QtCore import Qt
from ui.styles import CP


# ── Configurations par module ─────────────────────────────────────────────────
# Chaque entrée : (label_fr, suffix_en)

CASTING_CONTROLS = {
    "Style visuel": [
        ("Photoréaliste",   "photorealistic, cinematic photography"),
        ("Peinture",        "oil painting, painterly style"),
        ("Comics",          "comic book art, graphic novel style"),
        ("Aquarelle",       "watercolor illustration"),
        ("Rendu 3D",        "3D render, octane render, CGI"),
        ("Croquis",         "pencil sketch, hand-drawn illustration"),
    ],
    "Éclairage": [
        ("Studio",          "professional studio lighting, softbox light"),
        ("Naturel",         "natural daylight, outdoor ambient light"),
        ("Dramatique",      "dramatic Rembrandt lighting, deep shadows"),
        ("Cinéma",          "cinematic motivated lighting, key and fill"),
        ("Golden Hour",     "golden hour warm sunlight, magic hour glow"),
        ("Néon",            "neon glow, cyberpunk colored lights"),
    ],
    "Ambiance": [
        ("Héroïque",        "heroic, powerful, determined expression"),
        ("Mystérieux",      "mysterious, enigmatic, shadowy presence"),
        ("Sombre",          "brooding, intense, dark mood"),
        ("Charismatique",   "charismatic, confident, magnetic personality"),
        ("Épique",          "epic, majestic, cinematic gravitas"),
        ("Neutre",          "neutral expression, clean reference"),
    ],
}

DECOR_CONTROLS = {
    "Heure du jour": [
        ("Aube",            "dawn, first light, soft pink horizon"),
        ("Matin",           "morning light, soft daylight, long shadows"),
        ("Midi",            "noon, harsh midday sun, no shadows"),
        ("Golden Hour",     "golden hour, warm sunset glow"),
        ("Crépuscule",      "dusk, twilight, blue hour, fading light"),
        ("Nuit",            "night scene, moonlight, artificial lights"),
    ],
    "Météo": [
        ("Ensoleillé",      "clear sky, bright sunshine"),
        ("Brumeux",         "foggy, misty atmosphere, low visibility"),
        ("Nuageux",         "overcast, cloudy, diffused light"),
        ("Pluvieux",        "rain, wet surfaces, puddles, reflections"),
        ("Orageux",         "stormy, dramatic sky, lightning"),
        ("Neigeux",         "snow, winter frost, icy surfaces"),
    ],
    "Saison": [
        ("Printemps",       "spring, blooming flowers, fresh greenery"),
        ("Été",             "summer, lush vegetation, dry heat"),
        ("Automne",         "autumn, fallen leaves, warm orange tones"),
        ("Hiver",           "winter, bare trees, cold desaturated tones"),
    ],
    "Ambiance": [
        ("Abandonné",       "abandoned, decayed, overgrown, forgotten"),
        ("Animé",           "busy, lively, active, populated space"),
        ("Mystérieux",      "eerie, atmospheric, mysterious, uncanny"),
        ("Chaleureux",      "warm, welcoming, cozy, inviting"),
        ("Épique",          "grand scale, majestic, awe-inspiring"),
    ],
}

ACCESSORY_CONTROLS = {
    "Matière": [
        ("Métal",           "metal, steel, iron, metallic texture"),
        ("Cuir",            "genuine leather, stitched leather"),
        ("Tissu",           "fabric, textile, woven cloth"),
        ("Bois",            "wood, timber, carved wooden"),
        ("Or",              "gold, gilded, golden finish"),
        ("Argent",          "silver, chrome, polished silver"),
        ("Pierre",          "stone, carved rock, mineral"),
        ("Plastique",       "plastic, polymer, synthetic material"),
    ],
    "État": [
        ("Neuf",            "brand new, pristine, mint condition"),
        ("Usé",             "worn, used, natural patina"),
        ("Vieilli",         "aged, antique, weathered surface"),
        ("Abîmé",           "damaged, battle-worn, dented, scarred"),
        ("Poli",            "polished, shiny, mirror-like reflection"),
        ("Mat",             "matte finish, flat non-reflective surface"),
    ],
    "Vue": [
        ("Face",            "front view, straight on"),
        ("3/4",             "three-quarter angle view"),
        ("Profil",          "side profile view"),
        ("Détail",          "close-up macro detail shot"),
    ],
}

HMC_CONTROLS = {
    "Époque": [
        ("Contemporain",    "contemporary modern style"),
        ("Années 80",       "1980s retro style, synth-wave aesthetic"),
        ("Années 70",       "1970s style, groovy, vintage"),
        ("Médiéval",        "medieval historical period"),
        ("Victorien",       "Victorian era, 19th century"),
        ("Futuriste",       "futuristic, sci-fi, high-tech aesthetic"),
    ],
    "Style": [
        ("Haute Couture",   "haute couture, runway fashion, designer"),
        ("Casual",          "casual everyday wear, relaxed"),
        ("Formel",          "formal wear, elegant, dress code"),
        ("Streetwear",      "streetwear, urban fashion, sneaker culture"),
        ("Fantaisie",       "fantasy costume, theatrical, dramatic"),
        ("Sport",           "athletic wear, performance fabric"),
    ],
    "Palette couleurs": [
        ("Chaud",           "warm color palette, reds, oranges, yellows"),
        ("Froid",           "cool color palette, blues, greens, purples"),
        ("Neutre",          "neutral tones, beige, grey, taupe"),
        ("Monochrome",      "monochromatic, single color tones"),
        ("Vif",             "vibrant saturated colors, high chroma"),
        ("Pastel",          "pastel shades, soft muted tones"),
    ],
}

VEHICLE_CONTROLS = {
    "État": [
        ("Neuf",            "brand new showroom condition, perfect"),
        ("Usé",             "used, road-worn, everyday patina"),
        ("Endommagé",       "battle-damaged, crashed, dented, broken"),
        ("Vintage",         "vintage, classic, retro era styling"),
        ("Modifié",         "custom modified, tuned, personalized build"),
    ],
    "Finition": [
        ("Brillant",        "gloss paint, shiny lacquer finish"),
        ("Mat",             "matte paint, flat non-reflective finish"),
        ("Chromé",          "chrome finish, mirror polish, reflective"),
        ("Rouillé",         "rust patina, oxidized metal, weathered"),
        ("Carbone",         "carbon fiber panels, racing aesthetic"),
        ("Militaire",       "military matte finish, camouflage"),
    ],
    "Vue": [
        ("3/4 Avant",       "three-quarter front angle"),
        ("Face",            "front view, head-on"),
        ("Profil",          "side profile view, lateral"),
        ("3/4 Arrière",     "three-quarter rear angle"),
        ("Dessus",          "top-down aerial view"),
    ],
}


# ── Widget ────────────────────────────────────────────────────────────────────

class CreativeControlsPanel(QWidget):
    """
    Panneau collapsible de chips créatifs.
    Chaque section affiche des options à bascule (toggle).
    get_suffix() retourne les options actives en anglais (pour le prompt IA).
    """

    def __init__(self, controls: dict, parent=None):
        """
        controls : dict { section_label_fr: [(label_fr, suffix_en), ...] }
        """
        super().__init__(parent)
        self._chips: list[tuple[str, str, QPushButton]] = []  # (section, suffix_en, btn)
        self._selected: dict[str, set[str]] = {s: set() for s in controls}
        self._build(controls)

    # ── Construction ─────────────────────────────────────────────────────────

    def _build(self, controls: dict):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 0)
        outer.setSpacing(0)

        # ── En-tête toggle ────────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        self._toggle_btn = QPushButton("▶  Contrôles créatifs")
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setFixedHeight(28)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet(
            f"QPushButton{{color:{CP['text_secondary']};font-size:11px;font-weight:600;"
            f"background:transparent;border:none;text-align:left;padding:0;}}"
            f"QPushButton:hover{{color:{CP['text_primary']};}}"
        )
        self._toggle_btn.clicked.connect(self._toggle)
        header.addWidget(self._toggle_btn)

        self._reset_btn = QPushButton("Réinitialiser")
        self._reset_btn.setFixedHeight(20)
        self._reset_btn.setVisible(False)
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_btn.setStyleSheet(
            f"QPushButton{{color:{CP['text_dim']};font-size:10px;background:transparent;"
            f"border:none;padding:0 4px;}}"
            f"QPushButton:hover{{color:{CP['text_secondary']};}}"
        )
        self._reset_btn.clicked.connect(self.reset)
        header.addWidget(self._reset_btn)
        header.addStretch()

        outer.addLayout(header)

        # ── Conteneur collapsible ─────────────────────────────────────────────
        self._container = QWidget()
        self._container.setVisible(False)
        c_lay = QVBoxLayout(self._container)
        c_lay.setContentsMargins(0, 6, 0, 0)
        c_lay.setSpacing(8)

        for section, options in controls.items():
            sec_lbl = QLabel(section.upper())
            sec_lbl.setStyleSheet(
                f"color:{CP['text_dim']};font-size:9px;font-weight:700;letter-spacing:1px;"
                f"background:transparent;border:none;"
            )
            c_lay.addWidget(sec_lbl)

            chips_wrap = QWidget()
            chips_lay = QHBoxLayout(chips_wrap)
            chips_lay.setContentsMargins(0, 0, 0, 0)
            chips_lay.setSpacing(5)
            chips_lay.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            for label_fr, suffix_en in options:
                btn = QPushButton(label_fr)
                btn.setCheckable(True)
                btn.setFixedHeight(24)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(self._chip_style(False))
                btn.toggled.connect(
                    lambda checked, s=section, e=suffix_en, b=btn:
                    self._on_toggle(s, e, checked, b)
                )
                self._chips.append((section, suffix_en, btn))
                chips_lay.addWidget(btn)

            c_lay.addWidget(chips_wrap)

        outer.addWidget(self._container)

    # ── Style des chips ────────────────────────────────────────────────────────

    def _chip_style(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton{{background:{CP['accent_dim']};color:{CP['accent']};"
                f"border:1px solid {CP['accent']};border-radius:12px;"
                f"font-size:11px;padding:0 10px;font-weight:600;}}"
                f"QPushButton:hover{{background:rgba(0,200,180,0.22);}}"
            )
        return (
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:12px;"
            f"font-size:11px;padding:0 10px;}}"
            f"QPushButton:hover{{background:{CP['bg4']};color:{CP['text_primary']};"
            f"border-color:{CP['border_bright']};}}"
        )

    # ── Interactions ──────────────────────────────────────────────────────────

    def _on_toggle(self, section: str, suffix: str, checked: bool, btn: QPushButton):
        if checked:
            self._selected[section].add(suffix)
        else:
            self._selected[section].discard(suffix)
        btn.setStyleSheet(self._chip_style(checked))
        self._update_reset_visibility()

    def _toggle(self):
        visible = not self._container.isVisible()
        self._container.setVisible(visible)
        self._reset_btn.setVisible(visible)
        arrow = "▼" if visible else "▶"
        self._toggle_btn.setText(f"{arrow}  Contrôles créatifs")

    def _update_reset_visibility(self):
        has_any = any(v for v in self._selected.values())
        self._reset_btn.setVisible(has_any and self._container.isVisible())

    # ── API publique ──────────────────────────────────────────────────────────

    def get_suffix(self) -> str:
        """Retourne les options actives sous forme de chaîne anglaise séparée par des virgules."""
        parts: list[str] = []
        for section_selected in self._selected.values():
            parts.extend(section_selected)
        return ", ".join(parts)

    def reset(self):
        """Désélectionne tous les chips."""
        for section in self._selected:
            self._selected[section].clear()
        for _sec, _suf, btn in self._chips:
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.setStyleSheet(self._chip_style(False))
            btn.blockSignals(False)
        self._reset_btn.setVisible(False)


# ── Nouveau panneau slider ─────────────────────────────────────────────────────

class NanoBananaControlsPanel(QWidget):
    """Contrôle de liberté créative — slider 1-10 (Strict → Libre).

    Usage :
        self._creative = NanoBananaControlsPanel()
        lay.addWidget(self._creative)
        suffix = self._creative.get_prompt_suffix()  # injecté dans le prompt
    """

    _DESCS = [
        "",
        "Expérimental  —  Liberté créative maximale",
        "Très libre  —  Interprétation artistique affirmée",
        "Libre  —  Grande liberté créative",
        "Créatif  —  Interprétation libre du prompt",
        "Souple  —  Interprétation nuancée du prompt",
        "Équilibré  —  Latitude artistique raisonnable",
        "Fidèle  —  Légère latitude sur les détails mineurs",
        "Précis  —  Respecte strictement le prompt",
        "Strict  —  Composition précise et contrôlée",
        "Très strict  —  Reproduction fidèle, sans interprétation",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 0)
        outer.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        self._toggle_btn = QPushButton("▶  Liberté créative")
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setFixedHeight(28)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet(
            f"QPushButton{{color:{CP['text_secondary']};font-size:11px;font-weight:600;"
            f"background:transparent;border:none;text-align:left;padding:0;}}"
            f"QPushButton:hover{{color:{CP['text_primary']};}}"
        )
        self._toggle_btn.clicked.connect(self._toggle)
        header.addWidget(self._toggle_btn)
        header.addStretch()
        outer.addLayout(header)

        self._container = QWidget()
        self._container.setVisible(False)
        c_lay = QVBoxLayout(self._container)
        c_lay.setContentsMargins(0, 8, 0, 4)
        c_lay.setSpacing(6)

        labels_row = QHBoxLayout()
        for txt in ("Libre", "Strict"):
            lbl = QLabel(txt)
            lbl.setStyleSheet(
                f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;"
            )
            labels_row.addWidget(lbl)
            if txt == "Libre":
                labels_row.addStretch()
        c_lay.addLayout(labels_row)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(1, 10)
        self._slider.setValue(5)
        self._slider.setFixedHeight(22)
        self._slider.setStyleSheet(
            f"QSlider::groove:horizontal{{height:4px;background:{CP['bg3']};border-radius:2px;}}"
            f"QSlider::handle:horizontal{{width:14px;height:14px;"
            f"background:{CP['accent']};border-radius:7px;margin:-5px 0;}}"
            f"QSlider::sub-page:horizontal{{background:{CP['accent_dim']};border-radius:2px;}}"
        )
        self._slider.valueChanged.connect(self._on_value)
        c_lay.addWidget(self._slider)

        self._desc_lbl = QLabel(self._DESCS[5])
        self._desc_lbl.setWordWrap(True)
        self._desc_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;background:transparent;border:none;"
        )
        c_lay.addWidget(self._desc_lbl)
        outer.addWidget(self._container)

    def _toggle(self):
        v = not self._container.isVisible()
        self._container.setVisible(v)
        self._toggle_btn.setText(f"{'▼' if v else '▶'}  Liberté créative")

    def _on_value(self, v: int):
        self._desc_lbl.setText(self._DESCS[v] if 0 < v <= 10 else "")

    def get_creativity(self) -> int:
        return self._slider.value()

    def get_prompt_suffix(self) -> str:
        """Retourne un suffix anglais basé sur le niveau de créativité (1=libre, 10=strict)."""
        v = self._slider.value()
        if v <= 2:
            return "highly creative, artistic reinterpretation, imaginative expressive style"
        if v <= 4:
            return "creative freedom, artistic interpretation"
        if v >= 9:
            return "strict faithful reproduction, precise controlled composition"
        if v >= 7:
            return "faithful to reference, controlled composition"
        return ""  # 5-6 : neutre

    def get_suffix(self) -> str:
        return self.get_prompt_suffix()
