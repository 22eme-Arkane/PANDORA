"""api/staging_vision.py — Analyse VISION du plan de mise en scène par Claude.

Le PLAN VU DE DESSUS du décor (image créée avec Kontext, où le mobilier — table,
chaises… — est visible) + les positions normalisées des jetons (caméra, personnages,
projecteurs) sont envoyés à Claude Vision (Haiku). Claude corrèle les positions au
mobilier réellement visible et renvoie une description cinéma PRÉCISE :
  · mode staging → où est CHAQUE personnage par rapport au mobilier (« assise à la
    table, côté gauche »), et d'où filme la caméra ;
  · mode feu     → d'où vient la lumière par rapport à la scène + l'ambiance.

Sert à enrichir AUTOMATIQUEMENT les sections [MISE EN SCÈNE] / [PLAN DE FEU] du
prompt, en complément du placement déterministe instantané. Aucune clé Anthropic →
finished("") (l'appelant garde la version déterministe). La VISION reste sur
Anthropic (cf. api/real._analyze_style_ref) — hors couche core/ai_provider (texte).
"""

import base64
import mimetypes
import os

from PyQt6.QtCore import QThread, pyqtSignal

from core.config import load_config


def _img_block(path: str) -> dict:
    ext = os.path.splitext(path)[1].lower()
    mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".webp": "image/webp"}.get(ext, "image/png")
    with open(path, "rb") as f:
        b64 = base64.standard_b64encode(f.read()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}}


def _positions_text(tokens: list) -> str:
    """Liste lisible des positions (en % de la largeur/hauteur, origine haut-gauche)."""
    def pct(v):
        return f"{int(round(float(v) * 100))} %"
    cam    = [t for t in tokens if t.get("kind") == "camera"]
    actors = [t for t in tokens if t.get("kind") == "actor"]
    lights = [t for t in tokens if t.get("kind") == "light"]
    lines = []
    if cam:
        c = cam[0]
        info = f" — {c['info']}" if c.get("info") else ""
        lines.append(f"Caméra en ({pct(c.get('x', .5))}, {pct(c.get('y', .5))}){info}")
    for a in actors:
        lines.append(f"Personnage « {a.get('label', '?')} » en "
                     f"({pct(a.get('x', .5))}, {pct(a.get('y', .5))})")
    for l in lights:
        info = f" — {l['info']}" if l.get("info") else ""
        lines.append(f"Projecteur « {l.get('label', '')} » en "
                     f"({pct(l.get('x', .5))}, {pct(l.get('y', .5))}){info}")
    return "\n".join(lines)


class StagingVisionWorker(QThread):
    """Analyse le plan + les positions → description cinéma précise (FR)."""
    finished = pyqtSignal(str)   # texte précis (ou "" si indisponible)
    failed   = pyqtSignal(str)

    def __init__(self, plan_image: str, tokens: list, mode: str = "staging",
                 decor_desc: str = ""):
        super().__init__()
        self._plan  = plan_image
        self._tokens = tokens or []
        self._mode  = mode
        self._decor = decor_desc or ""

    def run(self):
        try:
            key = load_config().get("anthropic_key", "").strip()
            if not key or not (self._plan and os.path.isfile(self._plan)) or not self._tokens:
                self.finished.emit("")        # pas de clé / pas de plan → déterministe seul
                return
            import anthropic

            positions = _positions_text(self._tokens)
            if self._mode == "staging":
                ask = (
                    "Décris en français, en 1 à 3 phrases courtes et concrètes, où se trouve "
                    "CHAQUE personnage PAR RAPPORT au mobilier réellement visible sur le plan "
                    "(ex. « Magalie est assise à la table, côté gauche ; Jean lui fait face de "
                    "l'autre côté de la table ») et d'OÙ filme la caméra. N'écris AUCUN "
                    "pourcentage et aucun jargon technique. Réponds UNIQUEMENT par la description.")
            else:
                ask = (
                    "Décris en français, en 1 à 2 phrases, d'OÙ vient la lumière par rapport à "
                    "la scène et au mobilier visible, et l'ambiance qu'elle crée (douce ou dure, "
                    "chaude ou froide). N'écris AUCUN pourcentage et aucun nom de matériel. "
                    "Réponds UNIQUEMENT par la description.")
            intro = (
                "Voici un PLAN VU DE DESSUS d'un décor (le mobilier y est visible). Les "
                "positions ci-dessous sont en pourcentage de la largeur/hauteur, origine en "
                "haut à gauche.\n"
                + (f"Décor : {self._decor}\n" if self._decor else "")
                + positions + "\n\n" + ask)

            client = anthropic.Anthropic(api_key=key)
            msg = client.messages.create(
                model="claude-haiku-4-5", max_tokens=240,
                messages=[{"role": "user", "content": [
                    _img_block(self._plan),
                    {"type": "text", "text": intro},
                ]}],
            )
            self.finished.emit((msg.content[0].text or "").strip())
        except Exception as e:
            self.failed.emit(str(e)[:200])
