"""
resolume/client.py — Client REST pour Resolume Arena/Avenue (API Webserver).

⚠ Côté Resolume : Préférences → Webserver → activer le serveur web.
   (Rien à voir avec Wire, le logiciel de patching — confusion historique corrigée.)
   Par défaut le serveur écoute 0.0.0.0:8080 — en local : 127.0.0.1:8080.

Endpoints (doc : resolume.com/docs/restapi/) :
  GET  /api/v1/product                                    — infos produit/version
  GET  /api/v1/composition                                — composition complète
  POST /api/v1/composition/layers/{l}/clips/{c}/open     — charge un média
       body = URI fichier en TEXTE BRUT ("file:///C:/dir/clip.mp4") — PAS du JSON
  PUT  /api/v1/composition/layers/{l}/clips/{c}          — propriétés (nom…)
  POST /api/v1/composition/layers/{l}/clips/{c}/connect  — déclenche un clip
  POST /api/v1/composition/columns/{i}/connect           — déclenche une colonne
  PUT  /api/v1/composition                                — tempo composition (BPM)
  DELETE /api/v1/composition/layers/{l}/clips/{c}        — vide un slot

Indices layer/clip/colonne : 1-based (convention Resolume).
Style : chaque méthode renvoie bool/objet et n'élève JAMAIS — le détail du
dernier échec est dans `self.last_error` (affiché par l'UI/worker).
`session` est injectable pour les tests hors ligne du harnais.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080


def get_resolume_config() -> tuple:
    """(host, port) depuis config.json — défauts 127.0.0.1:8080."""
    from core.config import load_config
    cfg  = load_config()
    host = (cfg.get("resolume_host") or DEFAULT_HOST).strip() or DEFAULT_HOST
    try:
        port = int(cfg.get("resolume_port") or DEFAULT_PORT)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    return host, port


def file_uri(path: str) -> str:
    """Chemin Windows → URI fichier pour /open (file:///C:/dir/clip.mp4)."""
    p = os.path.abspath(path).replace("\\", "/")
    return f"file:///{p}" if not p.startswith("/") else f"file://{p}"


def set_choice_param(node, names: set, option_substring: str) -> bool:
    """Patch TOLÉRANT d'un paramètre « choix » dans le JSON d'un clip Resolume.

    Cherche récursivement une clé dont le nom ∈ `names` (insensible à la casse)
    portant un dict avec une liste "options", et sélectionne la première option
    contenant `option_substring`. Robuste aux variations de schéma entre
    versions d'Arena (manuel 7.x fourni par Matthieu, 2026-06-11) :
      - playmode  → "Play Once & Hold" (chaque plan joue une fois, tient sa frame)
      - beatsnap  → "1 Bar" (déclenchements quantisés à la mesure)
      - target (autopilot) → "Next clip" (la séquence s'enchaîne seule)
    Renvoie True si un paramètre a été modifié."""
    if isinstance(node, dict):
        for key, val in node.items():
            if (key.lower() in names and isinstance(val, dict)
                    and isinstance(val.get("options"), list)):
                opts = val["options"]
                for i, opt in enumerate(opts):
                    if option_substring.lower() in str(opt).lower():
                        val["index"] = i
                        val["value"] = opt
                        return True
            if set_choice_param(val, names, option_substring):
                return True
    elif isinstance(node, list):
        for item in node:
            if set_choice_param(item, names, option_substring):
                return True
    return False


def find_subtree(node, key: str):
    """Premier sous-dict porté par la clé `key` (insensible à la casse) — pour
    scoper un patch (ex. le « target » de l'AUTOPILOT, pas le Clip Target)."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k.lower() == key.lower():
                return v
            r = find_subtree(v, key)
            if r is not None:
                return r
    elif isinstance(node, list):
        for item in node:
            r = find_subtree(item, key)
            if r is not None:
                return r
    return None


@dataclass
class ClipInfo:
    layer:  int
    col:    int
    name:   str  = ""
    active: bool = False


@dataclass
class LayerInfo:
    index: int
    name:  str  = ""
    clips: list = field(default_factory=list)   # list[ClipInfo]


class ResolumeClient:
    """Client REST Resolume. Silencieux en cas d'échec (détail dans last_error)."""

    def __init__(self, host: str = "", port: int = 0, session=None):
        if not host or not port:
            c_host, c_port = get_resolume_config()
            host = host or c_host
            port = port or c_port
        self._base    = f"http://{host}:{port}/api/v1"
        self._timeout = 4
        self.last_error: str = ""
        if session is None:
            import requests
            session = requests.Session()
        self._s = session

    # ── Bas niveau ──────────────────────────────────────────────────────────────

    def _ok(self, resp) -> bool:
        code = getattr(resp, "status_code", 0)
        if code in (200, 204):
            return True
        self.last_error = f"Resolume a répondu {code} (le slot/la couche existe-t-il ?)"
        return False

    def _fail(self, e: Exception) -> bool:
        self.last_error = (f"connexion impossible ({e}) — Resolume est-il lancé, "
                           f"avec le Webserver activé (Préférences → Webserver) ?")
        return False

    # ── Connexion ──────────────────────────────────────────────────────────────

    def is_connected(self) -> bool:
        return bool(self.get_product_info())

    def get_product_info(self) -> dict:
        try:
            r = self._s.get(f"{self._base}/product", timeout=self._timeout)
            return r.json() if r.status_code == 200 else {}
        except Exception as e:
            self._fail(e)
            return {}

    # ── Composition ────────────────────────────────────────────────────────────

    def get_layers(self) -> list[LayerInfo]:
        """Couches + clips via GET /composition (la collection /layers seule
        n'est pas un endpoint fiable selon les versions)."""
        try:
            r = self._s.get(f"{self._base}/composition", timeout=self._timeout)
            if r.status_code != 200:
                self._ok(r)
                return []
            layers = []
            for i, ld in enumerate(r.json().get("layers", []), 1):
                name  = (ld.get("name") or {}).get("value", f"Layer {i}")
                clips = []
                for j, cd in enumerate(ld.get("clips", []), 1):
                    clip_name = (cd.get("name") or {}).get("value", "")
                    connected = (cd.get("connected") or {}).get("value", False)
                    clips.append(ClipInfo(layer=i, col=j, name=clip_name,
                                          active=bool(connected)))
                layers.append(LayerInfo(index=i, name=name, clips=clips))
            return layers
        except Exception as e:
            self._fail(e)
            return []

    # ── Contrôle ───────────────────────────────────────────────────────────────

    def trigger_clip(self, layer: int, col: int) -> bool:
        try:
            r = self._s.post(
                f"{self._base}/composition/layers/{layer}/clips/{col}/connect",
                timeout=self._timeout,
            )
            return self._ok(r)
        except Exception as e:
            return self._fail(e)

    def trigger_column(self, column: int) -> bool:
        try:
            r = self._s.post(
                f"{self._base}/composition/columns/{column}/connect",
                timeout=self._timeout,
            )
            return self._ok(r)
        except Exception as e:
            return self._fail(e)

    def load_clip(self, layer: int, col: int, file_path: str) -> bool:
        """Charge un média dans le slot. ⚠ Body = URI fichier en texte brut —
        l'ancien body JSON {"path": …} ne chargeait RIEN dans le vrai Arena."""
        try:
            r = self._s.post(
                f"{self._base}/composition/layers/{layer}/clips/{col}/open",
                data=file_uri(file_path).encode("utf-8"),
                headers={"Content-Type": "text/plain"},
                timeout=self._timeout,
            )
            return self._ok(r)
        except Exception as e:
            return self._fail(e)

    def set_clip_name(self, layer: int, col: int, name: str) -> bool:
        try:
            r = self._s.put(
                f"{self._base}/composition/layers/{layer}/clips/{col}",
                data=json.dumps({"name": {"value": name}}),
                headers={"Content-Type": "application/json"},
                timeout=self._timeout,
            )
            return self._ok(r)
        except Exception as e:
            return self._fail(e)

    def set_tempo(self, bpm: float) -> bool:
        """Règle le BPM de la composition (tempocontroller) — le calage PANDORA
        (mesures/drops) et les beat-snaps Resolume parlent alors le même tempo."""
        try:
            r = self._s.put(
                f"{self._base}/composition",
                data=json.dumps({"tempocontroller": {"tempo": {"value": float(bpm)}}}),
                headers={"Content-Type": "application/json"},
                timeout=self._timeout,
            )
            return self._ok(r)
        except Exception as e:
            return self._fail(e)

    def get_clip(self, layer: int, col: int) -> dict:
        """JSON complet d'un clip (pour patch tolérant des paramètres)."""
        try:
            r = self._s.get(f"{self._base}/composition/layers/{layer}/clips/{col}",
                            timeout=self._timeout)
            return r.json() if r.status_code == 200 else {}
        except Exception as e:
            self._fail(e)
            return {}

    def put_clip(self, layer: int, col: int, payload: dict) -> bool:
        """Réécrit le JSON d'un clip (après modification de paramètres)."""
        try:
            r = self._s.put(
                f"{self._base}/composition/layers/{layer}/clips/{col}",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=self._timeout,
            )
            return self._ok(r)
        except Exception as e:
            return self._fail(e)

    def clear_clip(self, layer: int, col: int) -> bool:
        try:
            r = self._s.delete(
                f"{self._base}/composition/layers/{layer}/clips/{col}",
                timeout=self._timeout,
            )
            return self._ok(r)
        except Exception as e:
            return self._fail(e)
