"""
resolume/client.py — Client REST pour Resolume Arena/Avenue (Wire API).

Resolume Wire API (activée depuis Resolume → Preferences → Wire) :
  GET  /api/v1/product                                           — infos version
  GET  /api/v1/composition/layers                               — toutes les couches + clips
  POST /api/v1/composition/layers/{n}/clips/{c}/connect         — déclencher un clip
  POST /api/v1/composition/layers/{n}/clips/{c}/open            — charger un fichier dans un slot
  DELETE /api/v1/composition/layers/{n}/clips/{c}               — vider un slot

Indices layer/clip : 1-based.
Port par défaut : 8080.
"""

from __future__ import annotations
from dataclasses import dataclass, field


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
    """Client REST Resolume Wire API. Chaque méthode est silencieuse en cas d'échec."""

    def __init__(self, host: str = "localhost", port: int = 8080):
        self._base    = f"http://{host}:{port}/api/v1"
        self._timeout = 3

    # ── Connexion ──────────────────────────────────────────────────────────────

    def is_connected(self) -> bool:
        return bool(self.get_product_info())

    def get_product_info(self) -> dict:
        try:
            import requests
            r = requests.get(f"{self._base}/product", timeout=self._timeout)
            return r.json() if r.status_code == 200 else {}
        except Exception:
            return {}

    # ── Composition ────────────────────────────────────────────────────────────

    def get_layers(self) -> list[LayerInfo]:
        try:
            import requests
            r = requests.get(f"{self._base}/composition/layers", timeout=self._timeout)
            if r.status_code != 200:
                return []
            layers = []
            for i, ld in enumerate(r.json().get("layers", []), 1):
                name  = ld.get("name", {}).get("value", f"Layer {i}")
                clips = []
                for j, cd in enumerate(ld.get("clips", []), 1):
                    clip_name = cd.get("name", {}).get("value", "")
                    connected = cd.get("connected", {}).get("value", False)
                    clips.append(ClipInfo(layer=i, col=j, name=clip_name, active=connected))
                layers.append(LayerInfo(index=i, name=name, clips=clips))
            return layers
        except Exception:
            return []

    # ── Contrôle ───────────────────────────────────────────────────────────────

    def trigger_clip(self, layer: int, col: int) -> bool:
        try:
            import requests
            r = requests.post(
                f"{self._base}/composition/layers/{layer}/clips/{col}/connect",
                timeout=self._timeout,
            )
            return r.status_code in (200, 204)
        except Exception:
            return False

    def load_clip(self, layer: int, col: int, file_path: str) -> bool:
        try:
            import requests
            r = requests.post(
                f"{self._base}/composition/layers/{layer}/clips/{col}/open",
                json={"path": file_path.replace("\\", "/")},
                timeout=self._timeout,
            )
            return r.status_code in (200, 204)
        except Exception:
            return False

    def clear_clip(self, layer: int, col: int) -> bool:
        try:
            import requests
            r = requests.delete(
                f"{self._base}/composition/layers/{layer}/clips/{col}",
                timeout=self._timeout,
            )
            return r.status_code in (200, 204)
        except Exception:
            return False
