"""Contrat éditorial du Découpage PANDORA 2.

Le scénario reste la vérité narrative et la note de réalisation porte les intentions
globales. Le découpage ne recopie plus une fausse page de scénario bardée de technique :
chaque plan est une fiche de préparation indépendante, lisible et transformable en
plan de storyboard sans nouvel appel IA.

Le format reste textuel pour être éditable dans l'application et portable dans les
anciens fichiers de projet. Les libellés explicites remplacent l'ancien en-tête compact
``P01 | valeur | mouvement | axe | ~durée``.
"""

from __future__ import annotations

import re


VERSION_MARKER = "DÉCOUPAGE PANDORA 2"

_PLAN_RE = re.compile(r"^PLAN\s+0*(\d{1,3})\s*$", re.IGNORECASE | re.MULTILINE)
_SEQ_RE = re.compile(
    r"^S[ÉE]QUENCE\s+0*(\d{1,3})\s*[—–:\-]?\s*(.*?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_LABELS = {
    "source": ("SOURCE SCÉNARIO", "SCREENPLAY SOURCE"),
    "intention": ("INTENTION", "INTENT"),
    "rhythm": ("RYTHME", "RHYTHM"),
    "duration": ("DURÉE", "DURATION"),
    "prompt": ("PROMPT VISUEL", "VISUAL PROMPT"),
    "characters": ("PERSONNAGES", "CHARACTERS"),
    "decor": ("DÉCOR", "SET"),
    "accessories": ("ACCESSOIRES", "PROPS"),
    "vehicles": ("VÉHICULES", "VEHICLES"),
    "hmc": ("HMC",),
    "shot_size": ("VALEUR PROPOSÉE", "SUGGESTED SHOT SIZE"),
    "camera_axis": ("AXE PROPOSÉ", "SUGGESTED AXIS"),
    "camera_movement": ("MOUVEMENT PROPOSÉ", "SUGGESTED MOVEMENT"),
    "focal": ("FOCALE PROPOSÉE", "SUGGESTED FOCAL LENGTH"),
    "mood": ("MOOD",),
}


def is_v2_document(text: str) -> bool:
    """Vrai pour un document utilisant réellement les fiches v2."""
    value = text or ""
    return bool(
        VERSION_MARKER in value.upper()
        and _PLAN_RE.search(value)
        and re.search(r"^(?:PROMPT VISUEL|VISUAL PROMPT)\s*:", value,
                      re.IGNORECASE | re.MULTILINE)
    )


def _label_pattern() -> re.Pattern:
    names = [re.escape(label) for aliases in _LABELS.values() for label in aliases]
    return re.compile(rf"^({'|'.join(names)})\s*:\s*", re.IGNORECASE | re.MULTILINE)


_ANY_LABEL_RE = _label_pattern()


def _field(block: str, key: str) -> str:
    aliases = "|".join(re.escape(v) for v in _LABELS[key])
    match = re.search(rf"^(?:{aliases})\s*:\s*(.*)$", block,
                      re.IGNORECASE | re.MULTILINE)
    if not match:
        return ""
    start = match.start(1)
    following = _ANY_LABEL_RE.search(block, match.end())
    end = following.start() if following else len(block)
    return block[start:end].strip().rstrip("—").strip()


def _list_field(value: str) -> list[str]:
    value = (value or "").strip()
    if not value or value in {"—", "-", "Aucun", "None"}:
        return []
    return [item.strip() for item in re.split(r"[,;]", value) if item.strip()]


def parse_v2_document(text: str) -> list[dict]:
    """Convertit les fiches v2 en segments déterministes pour le Storyboard."""
    if not is_v2_document(text):
        return []
    matches = list(_PLAN_RE.finditer(text or ""))
    sequences = list(_SEQ_RE.finditer(text or ""))
    segments: list[dict] = []
    for index, match in enumerate(matches):
        next_plan = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        # Une nouvelle séquence appartient au plan suivant. Sans cette borne, son
        # titre pouvait être absorbé par le dernier champ (MOOD) du plan précédent.
        next_sequences = [
            seq.start() for seq in sequences
            if match.end() < seq.start() < next_plan
        ]
        end = min([next_plan, *next_sequences])
        block = text[match.end():end]
        seq_num, seq_name = 1, ""
        preceding = [seq for seq in sequences if seq.start() < match.start()]
        if preceding:
            seq_num = int(preceding[-1].group(1))
            seq_name = preceding[-1].group(2).strip(" —–:-")
        duration_text = _field(block, "duration")
        duration_match = re.search(r"(\d+(?:[.,]\d+)?)", duration_text)
        duration = float(duration_match.group(1).replace(",", ".")) if duration_match else 5.0
        source = _field(block, "source")
        prompt = _field(block, "prompt")
        segments.append({
            "number": int(match.group(1)),
            "act": seq_num,
            "act_name": seq_name,
            "action": source or _field(block, "intention") or prompt,
            "source": source,
            "intention": _field(block, "intention"),
            "rhythm": _field(block, "rhythm"),
            "duration": duration,
            "prompt": prompt,
            "character_names": _list_field(_field(block, "characters")),
            "decor_name": _field(block, "decor"),
            "accessory_names": _list_field(_field(block, "accessories")),
            "vehicle_names": _list_field(_field(block, "vehicles")),
            "hmc_names": _list_field(_field(block, "hmc")),
            "shot_size": _field(block, "shot_size"),
            "camera_axis": _field(block, "camera_axis"),
            "camera_movement": _field(block, "camera_movement"),
            "focal": _field(block, "focal"),
            "mood": _field(block, "mood"),
        })
    return segments


def validate_v2_document(text: str) -> list[str]:
    """Erreurs bloquantes du contrat v2 ; les propositions caméra restent facultatives."""
    segments = parse_v2_document(text)
    if not segments:
        return ["structure_v2_non_reconnue"]
    errors: list[str] = []
    for segment in segments:
        label = f"PLAN {int(segment.get('number') or 0):02d}"
        duration = float(segment.get("duration") or 0)
        if duration < 2 or duration > 15:
            errors.append(f"{label}:durée")
        if not str(segment.get("source") or "").strip():
            errors.append(f"{label}:source")
        if not str(segment.get("intention") or "").strip():
            errors.append(f"{label}:intention")
        if not str(segment.get("prompt") or "").strip():
            errors.append(f"{label}:prompt_visuel")
    return errors


def blank_plan(number: int = 1, lang: str = "fr") -> str:
    """Fiche vierge utilisée par l'éditeur lors de l'ajout manuel d'un plan."""
    if lang == "en":
        return (
            f"PLAN {number:02d}\n"
            "SCREENPLAY SOURCE: Exact excerpt to preserve.\n"
            "INTENT: Dramatic and visual purpose of this shot.\n"
            "RHYTHM: Neutral.\n"
            "DURATION: 5s\n"
            "VISUAL PROMPT: Describe the image to prepare.\n"
            "CHARACTERS: —\nSET: —\nPROPS: —\nVEHICLES: —\nHMC: —\n"
            "SUGGESTED SHOT SIZE: —\nSUGGESTED AXIS: —\n"
            "SUGGESTED MOVEMENT: —\nSUGGESTED FOCAL LENGTH: —\nMOOD: TO CREATE"
        )
    return (
        f"PLAN {number:02d}\n"
        "SOURCE SCÉNARIO : Extrait exact à préserver.\n"
        "INTENTION : Fonction dramatique et visuelle de ce plan.\n"
        "RYTHME : Neutre.\n"
        "DURÉE : 5s\n"
        "PROMPT VISUEL : Décrire l'image à préparer.\n"
        "PERSONNAGES : —\nDÉCOR : —\nACCESSOIRES : —\nVÉHICULES : —\nHMC : —\n"
        "VALEUR PROPOSÉE : —\nAXE PROPOSÉ : —\n"
        "MOUVEMENT PROPOSÉ : —\nFOCALE PROPOSÉE : —\nMOOD : À CRÉER"
    )
