"""Reprojection d'un panorama équirectangulaire en vues perspective.

Sert au moteur « Panorama 360° (Hunyuan World) » de l'atelier 7 vues :
`fal-ai/hunyuan_world` produit un panorama équirectangulaire (ratio 2:1,
360° × 180°) ; les six vues du décor (Avant/Arrière/Gauche/Droite/Sol/
Plafond) sont ensuite des reprojections LOCALES (projection gnomonique) —
aucune génération supplémentaire, géométrie cohérente PAR CONSTRUCTION
(toutes les vues sortent du même panorama).

Module PUR (numpy + Pillow) : aucun réseau, aucun Qt.
"""

from __future__ import annotations

import math
import os


# (yaw, pitch) en degrés pour chaque code de vue PANDORA (core.room_views).
# yaw : 0 = avant, 90 = droite, 180 = arrière, 270 = gauche (vu de dessus,
# sens horaire). pitch : 0 = horizon, +90 = zénith (plafond), −90 = nadir (sol).
VIEW_ANGLES: dict[str, tuple[float, float]] = {
    "avant":   (0.0,    0.0),
    "droite":  (90.0,   0.0),
    "arriere": (180.0,  0.0),
    "gauche":  (270.0,  0.0),
    "plafond": (0.0,   90.0),
    "sol":     (0.0,  -90.0),
}

# Champ de vision horizontal par défaut des vues extraites. 95° ≈ un très
# grand angle de repérage : chaque face couvre bien son mur sans trop
# d'anamorphose dans les coins.
DEFAULT_FOV = 95.0


def is_equirectangular_size(width: int, height: int) -> bool:
    """Un panorama équirectangulaire complet fait un ratio 2:1 (±10 %)."""
    if not (width and height):
        return False
    return abs((width / height) - 2.0) <= 0.2


def render_view(pano, yaw_deg: float, pitch_deg: float,
                fov_deg: float = DEFAULT_FOV,
                out_w: int = 1344, out_h: int = 756):
    """Reprojette une vue perspective depuis un panorama équirectangulaire.

    pano : PIL.Image (RGB). Renvoie une PIL.Image (out_w × out_h).
    Échantillonnage bilinéaire, enroulement horizontal (360°), bord vertical
    borné (les pôles s'étirent — propriété de la projection, pas un bug).
    """
    import numpy as np
    from PIL import Image

    src = np.asarray(pano.convert("RGB"), dtype=np.float32)
    H, W = src.shape[0], src.shape[1]

    # Directions caméra pour chaque pixel de sortie (repère : X droite,
    # Y haut, Z avant), plan image à z = 1.
    half = math.tan(math.radians(fov_deg) / 2.0)
    half_v = half * out_h / out_w
    xs = (2.0 * (np.arange(out_w, dtype=np.float32) + 0.5) / out_w - 1.0) * half
    ys = (1.0 - 2.0 * (np.arange(out_h, dtype=np.float32) + 0.5) / out_h) * half_v
    dx, dy = np.meshgrid(xs, ys)
    dz = np.ones_like(dx)

    # Rotation PITCH (autour de X ; +90° = regarder le zénith)…
    p = math.radians(pitch_deg)
    cy, sy = math.cos(p), math.sin(p)
    dy2 = dy * cy + dz * sy
    dz2 = -dy * sy + dz * cy
    # …puis YAW (autour de Y ; +90° = tourner vers la droite).
    a = math.radians(yaw_deg)
    ca, sa = math.cos(a), math.sin(a)
    dx3 = dx * ca + dz2 * sa
    dz3 = -dx * sa + dz2 * ca

    # Direction → (longitude, latitude) → coordonnées panorama.
    norm = np.sqrt(dx3 * dx3 + dy2 * dy2 + dz3 * dz3)
    lon = np.arctan2(dx3, dz3)                      # (−π, π], 0 = avant
    lat = np.arcsin(np.clip(dy2 / norm, -1.0, 1.0))  # [−π/2, π/2]
    u = (lon / (2.0 * math.pi) + 0.5) * W - 0.5     # colonne (enroulée)
    v = (0.5 - lat / math.pi) * H - 0.5             # ligne (0 = zénith)

    # Bilinéaire : 4 voisins, poids fractionnaires.
    u0 = np.floor(u).astype(np.int64)
    v0 = np.floor(v).astype(np.int64)
    fu = (u - u0)[..., None]
    fv = (v - v0)[..., None]
    u0w = np.mod(u0, W)
    u1w = np.mod(u0 + 1, W)
    v0c = np.clip(v0, 0, H - 1)
    v1c = np.clip(v0 + 1, 0, H - 1)
    top = src[v0c, u0w] * (1.0 - fu) + src[v0c, u1w] * fu
    bot = src[v1c, u0w] * (1.0 - fu) + src[v1c, u1w] * fu
    out = top * (1.0 - fv) + bot * fv
    return Image.fromarray(np.clip(out + 0.5, 0, 255).astype("uint8"), "RGB")


def render_views(pano_path: str, out_dir: str, base_name: str,
                 fov_deg: float = DEFAULT_FOV,
                 codes: list[str] | None = None,
                 out_w: int = 1344, out_h: int = 756) -> list[tuple[str, str]]:
    """Reprojette les vues demandées et les écrit en PNG.

    Renvoie [(code, chemin), …] dans l'ordre demandé. `base_name` est
    assaini pour servir de préfixe de fichier.
    """
    from PIL import Image
    import time as _t

    pano = Image.open(pano_path)
    os.makedirs(out_dir, exist_ok=True)
    safe = "".join(c for c in (base_name or "pano")
                   if c.isalnum() or c in " -_").strip() or "pano"
    ts = int(_t.time())
    out: list[tuple[str, str]] = []
    for code in (codes or list(VIEW_ANGLES)):
        yaw, pitch = VIEW_ANGLES[code]
        # Sol/Plafond : cadre carré (une face vue perpendiculairement n'a pas
        # de « largeur » privilégiée), les faces murales restent en 16:9.
        square = code in ("sol", "plafond")
        w, h = (out_h, out_h) if square else (out_w, out_h)
        img = render_view(pano, yaw, pitch, fov_deg, w, h)
        path = os.path.join(out_dir, f"{safe}_{code}_{ts}.png")
        img.save(path, "PNG")
        out.append((code, path))
    return out
