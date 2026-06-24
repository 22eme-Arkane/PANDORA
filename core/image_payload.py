"""
core/image_payload.py — Préparation d'images pour les appels VISION (partagé).

Cause du « 413 request_too_large » : les photos partaient en PLEINE RÉSOLUTION
(une photo de téléphone ≈ 3-8 Mo, ×1,33 en base64 — quelques images suffisent à
dépasser la limite de l'API). Anthropic recommande ≤ 1568 px de grand côté : on
redimensionne et recompresse AVANT l'envoi (~150-400 Ko par image, sans perte
utile pour l'analyse).
"""

import base64
import io
import os

MAX_SIDE = 1568          # recommandation Anthropic Vision
JPEG_QUALITY = 85


def encode_image_for_vision(path: str, max_side: int = MAX_SIDE,
                            quality: int = JPEG_QUALITY) -> tuple:
    """(mime, base64) prêt pour l'API vision — image redimensionnée/recompressée.
    Repli sur le fichier brut si Pillow échoue."""
    try:
        from PIL import Image
        img = Image.open(path)
        img.load()
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        w, h = img.size
        scale = max_side / max(w, h)
        if scale < 1.0:
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))),
                             Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=quality, optimize=True)
        return "image/jpeg", base64.standard_b64encode(buf.getvalue()).decode()
    except Exception:
        import mimetypes
        mime = mimetypes.guess_type(path)[0] or "image/jpeg"
        with open(path, "rb") as f:
            return mime, base64.standard_b64encode(f.read()).decode()
