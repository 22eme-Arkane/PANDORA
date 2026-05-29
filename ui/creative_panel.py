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
from ui.styles import CP, C


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

I2V_CONTROLS = {
    "Style visuel": [
        ("Cinématique",     "cinematic film look, anamorphic lens, shallow depth of field"),
        ("Photoréaliste",   "photorealistic, ultra-detailed, high fidelity"),
        ("Noir & blanc",    "black and white, monochrome, film noir aesthetic"),
        ("Animation",       "animation style, stylized, illustrated"),
        ("Vintage",         "vintage film grain, retro aesthetic, aged look"),
        ("Néon",            "neon glow, cyberpunk, vivid saturated colors"),
    ],
    "Mouvement caméra": [
        ("Fixe",            "static shot, locked camera, no movement"),
        ("Dolly",           "dolly shot, smooth forward camera movement"),
        ("Pan",             "camera pan, horizontal sweep"),
        ("Handheld",        "handheld camera, slight shake, documentary feel"),
        ("Drone",           "drone shot, aerial perspective"),
        ("Zoom lent",       "slow zoom, subtle lens zoom movement"),
    ],
    "Éclairage": [
        ("Naturel",         "natural daylight, outdoor ambient light"),
        ("Dramatique",      "dramatic chiaroscuro, deep shadows, high contrast"),
        ("Golden Hour",     "golden hour, warm sunset glow, magic hour"),
        ("Nuit",            "night scene, artificial lights, low-key lighting"),
        ("Studio",          "professional studio lighting, clean, controlled"),
        ("Contrejour",      "backlit, silhouette, contre-jour, rim light"),
    ],
    "Ambiance": [
        ("Épique",          "epic, grand, cinematic gravitas"),
        ("Calme",           "calm, serene, peaceful, contemplative"),
        ("Intense",         "intense, high energy, dynamic, fast-paced"),
        ("Mystérieux",      "mysterious, eerie, atmospheric, uncanny"),
        ("Émotionnel",      "emotional, intimate, heartfelt, tender"),
        ("Futuriste",       "futuristic, sci-fi, high-tech, sleek"),
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


# ── Contrôles créatifs Seedance — sliders (partagé T2V + DaVinci edit) ────────

_SDANCE_DEFS = [
    # (key, group, fr_label, left_pole, right_pole, {pos: english_phrase})
    # pos=3 est neutre → pas injecté
    ("prompt_adherence", "RÉALISATION", "Interprétation", "Créatif",   "Littéral", {
        1: "experimental free cinematic interpretation, prioritize visual impact over literal faithfulness",
        2: "loose creative adaptation, loosely inspired by the prompt",
        4: "close to the prompt with minor artistic liberties",
        5: "strictly faithful to the prompt description, literal visual rendering",
    }),
    ("camera_motion",    "RÉALISATION", "Caméra",         "Fixe",      "Dynamique", {
        1: "completely static camera, locked tripod, absolutely no camera movement",
        2: "very subtle camera movement, nearly static",
        4: "active camera movement, noticeable dynamic motion",
        5: "highly dynamic handheld camera, fast kinetic movement",
    }),
    ("motion_strength",  "RÉALISATION", "Mouvement",      "Subtil",    "Intense", {
        1: "minimal movement, near-static scene, very subtle micro-motions only",
        2: "gentle subtle motion, low scene dynamics, soft gentle movement",
        4: "strong visual dynamics, active motion, significant scene transformation",
        5: "maximum motion intensity, extreme visual transformation, full kinetic energy",
    }),
    ("drama_level",      "RÉALISATION", "Atmosphère",     "Calme",     "Dramatique", {
        1: "calm peaceful atmosphere, minimal drama, serene quiet mood",
        2: "relaxed tone, mild gentle tension",
        4: "strong dramatic tension, intense cinematic atmosphere",
        5: "strong drama, high tension, deeply intense cinematic atmosphere",
    }),
    ("action_pace",      "RÉALISATION", "Rythme",         "Lent",      "Rapide", {
        1: "very slow contemplative rhythm, long slow takes",
        2: "slow calm pace, deliberate unhurried timing",
        4: "fast-paced energetic rhythm, quick action",
        5: "very fast pace, high-energy rapid action sequence",
    }),
    ("lighting_contrast","RÉALISATION", "Lumière",        "Douce",     "Contrastée", {
        1: "very soft diffused lighting, no harsh shadows, flat even illumination",
        2: "soft natural lighting, gentle soft shadows",
        4: "strong contrast, deep shadows, crisp bright highlights",
        5: "strong high contrast, dramatic chiaroscuro lighting",
    }),
    ("temporal_coherence","FIDÉLITÉ",   "Cohérence",      "Variable",  "Stable", {
        1: "allow temporal discontinuities and dreamlike visual transitions",
        2: "slightly loose temporal flow, some visual variation allowed",
        4: "strong temporal coherence, smooth consistent motion flow",
        5: "maximum temporal stability, perfectly consistent motion, no flickering",
    }),
    ("realism",          "ESTHÉTIQUE",  "Rendu",          "Stylisé",   "Réaliste", {
        1: "highly stylized surreal aesthetic, artistic painterly visual treatment",
        2: "stylized look with graphic or painterly quality",
        4: "mostly realistic with subtle cinematic treatment",
        5: "photorealistic documentary-style natural rendering",
    }),
    ("visual_density",   "ESTHÉTIQUE",  "Composition",    "Épurée",    "Riche", {
        1: "minimalist composition, clean empty frame, single subject focus",
        2: "simple clean composition, few visual elements",
        4: "rich detailed composition, many visual elements",
        5: "very dense visual composition, richly layered detail",
    }),
    ("depth_of_field",   "ESTHÉTIQUE",  "Prof. de champ", "Net",       "Flou", {
        1: "deep focus, everything sharp, infinite depth of field, all elements crisp",
        2: "moderate depth of field, slight background softness",
        4: "shallow depth of field, soft blurred background, subject isolation, cinematic bokeh",
        5: "extreme shallow depth of field, heavy bokeh, strong background blur, wide-aperture lens",
    }),
    ("saturation",       "ESTHÉTIQUE",  "Saturation",     "Désaturé",  "Éclatant", {
        1: "desaturated palette, muted dull tones, near-monochromatic, low chroma",
        2: "subdued colors, soft muted tones, slightly desaturated palette",
        4: "vivid saturated colors, rich chromatic intensity, punchy color grading",
        5: "hyper-saturated, extremely vivid colors, intense high-chroma palette",
    }),
]

_SDANCE_PHRASES = {d[0]: d[5] for d in _SDANCE_DEFS}


class SeedanceCreativePanel(QFrame):
    """
    Panneau collapsible de contrôles créatifs à sliders — même look que T2V.
    Usage :
        self._creative = SeedanceCreativePanel()
        lay.addWidget(self._creative)
        suffix = self._creative.get_creative_suffix()
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sdance_creative_panel")
        self.setStyleSheet(
            f"QFrame#sdance_creative_panel{{background:{C['bg1']};"
            f"border:1px solid {C['border']};border-radius:10px;}}"
        )
        self._expanded = False
        self._sliders: dict[str, QSlider] = {}
        self.setMaximumHeight(38)  # Réduit à l'en-tête quand replié

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── En-tête toggle ────────────────────────────────────────────────────
        self._header = QPushButton("⚙  Contrôles créatifs    ▶")
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setFixedHeight(36)
        self._header.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;"
            f"color:{C['text_secondary']};font-size:11px;font-weight:700;"
            f"text-align:left;padding:0 14px;}}"
            f"QPushButton:hover{{color:{C['text_primary']};}}"
        )
        self._header.clicked.connect(self._toggle)
        root.addWidget(self._header)

        # ── Corps collapsible ─────────────────────────────────────────────────
        self._body = QWidget()
        self._body.setVisible(False)
        body_lay = QVBoxLayout(self._body)
        body_lay.setContentsMargins(14, 4, 14, 12)
        body_lay.setSpacing(4)

        current_group = None
        for key, group, fr_label, left_pole, right_pole, _ in _SDANCE_DEFS:
            if group != current_group:
                current_group = group
                if body_lay.count() > 0:
                    body_lay.addSpacing(6)
                g_lbl = QLabel(group)
                g_lbl.setStyleSheet(
                    f"color:{C['text_dim']};font-size:9px;font-weight:700;"
                    f"font-family:'Consolas',monospace;letter-spacing:1px;background:transparent;"
                )
                body_lay.addWidget(g_lbl)
            body_lay.addLayout(self._make_row(key, fr_label, left_pole, right_pole))

        # Bouton réinitialiser
        body_lay.addSpacing(8)
        reset_row = QHBoxLayout()
        reset_row.addStretch()
        reset_btn = QPushButton("↺  Réinitialiser")
        reset_btn.setFixedHeight(26)
        reset_btn.setStyleSheet(
            f"QPushButton{{background:{C['bg3']};border:1px solid {C['border']};"
            f"border-radius:6px;color:{C['text_dim']};font-size:10px;padding:0 12px;}}"
            f"QPushButton:hover{{color:{C['text_primary']};border-color:{C['border_bright']};}}"
        )
        reset_btn.clicked.connect(self._reset)
        reset_row.addWidget(reset_btn)
        body_lay.addLayout(reset_row)

        root.addWidget(self._body)

    @staticmethod
    def _slider_style() -> str:
        return (
            f"QSlider::groove:horizontal{{height:4px;background:{C['bg3']};border-radius:2px;}}"
            f"QSlider::handle:horizontal{{width:12px;height:12px;margin:-4px 0;"
            f"background:{C['accent']};border-radius:6px;}}"
            f"QSlider::sub-page:horizontal{{background:{C['accent_dim']};border-radius:2px;}}"
        )

    def _make_row(self, key: str, fr_label: str,
                  left_pole: str, right_pole: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        row.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel(fr_label)
        lbl.setFixedWidth(82)
        lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:10px;background:transparent;")
        row.addWidget(lbl)

        left_lbl = QLabel(left_pole)
        left_lbl.setFixedWidth(46)
        left_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        left_lbl.setStyleSheet(f"color:{C['text_dim']};font-size:9px;background:transparent;")
        row.addWidget(left_lbl)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(1, 5)
        slider.setValue(3)
        slider.setFixedHeight(18)
        slider.setStyleSheet(self._slider_style())
        self._sliders[key] = slider
        row.addWidget(slider, 1)

        right_lbl = QLabel(right_pole)
        right_lbl.setFixedWidth(56)
        right_lbl.setStyleSheet(f"color:{C['text_dim']};font-size:9px;background:transparent;")
        row.addWidget(right_lbl)

        val_lbl = QLabel("·")
        val_lbl.setFixedWidth(16)
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val_lbl.setStyleSheet(
            f"color:{C['accent']};font-size:9px;font-weight:700;"
            f"font-family:'Consolas',monospace;background:transparent;"
        )
        row.addWidget(val_lbl)
        slider.valueChanged.connect(
            lambda v, l=val_lbl: l.setText("·" if v == 3 else str(v))
        )
        return row

    def _toggle(self):
        self._expanded = not self._expanded
        self._body.setVisible(self._expanded)
        arrow = "▼" if self._expanded else "▶"
        self._header.setText(f"⚙  Contrôles créatifs    {arrow}")
        self.setMaximumHeight(16777215 if self._expanded else 38)

    def _reset(self):
        for slider in self._sliders.values():
            slider.setValue(3)

    def get_creative_suffix(self) -> str:
        """Retourne les phrases anglaises des sliders non-neutres, séparées par des virgules."""
        parts = []
        for key, slider in self._sliders.items():
            v = slider.value()
            if v == 3:
                continue
            phrase = _SDANCE_PHRASES.get(key, {}).get(v, "")
            if phrase:
                parts.append(phrase)
        return ", ".join(parts)

    def get_suffix(self) -> str:
        return self.get_creative_suffix()
