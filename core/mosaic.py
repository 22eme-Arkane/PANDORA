"""
Builds composite reference images for Seedance by grouping multiple entity images
into labeled mosaics. Up to 3 mosaics are produced to fit Seedance's 3-image limit:

  slot 0 — Characters grid  (all selected characters, face/sheet + name)
  slot 1 — Decor            (location image, passed through as-is)
  slot 2 — Others grid      (accessories + vehicles, each with name — HMC excluded)

Requires Pillow. If Pillow is unavailable the functions fall back to returning
individual image paths (best-effort, up to 3).
"""

import os
import time

_CELL_W  = 210
_CELL_H  = 260
_LABEL_H = 34
_BG      = (22, 22, 26)
_BAR_BG  = (16, 16, 20)
_TEXT    = (215, 215, 225)
_PLACEHOLDER = (40, 40, 48)


def _has_real_transparency(path: str) -> bool:
    """True si l'image a une transparence RÉELLE (au moins un pixel alpha < 255) —
    c.-à-d. un portrait DÉTOURÉ. Un RGBA opaque (alpha plein) renvoie False."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            if im.mode == "P" and "transparency" in im.info:
                return True
            if im.mode in ("RGBA", "LA"):
                return im.getchannel("A").getextrema()[0] < 255
            return False
    except Exception:
        return False


def _pick_char_ref(char: dict) -> str:
    """Image de référence d'un personnage. Un portrait DÉTOURÉ (PNG transparent) PRIME
    sur la planche 4 vues (sheet_path), car celle-ci garde le fond d'origine — sinon
    Seedance reçoit l'ancien fond. À défaut de détourage, on garde la planche
    (multi-vues = meilleure cohérence), puis le portrait simple."""
    img   = char.get("image_path", "")
    sheet = char.get("sheet_path", "")
    if img and os.path.isfile(img) and _has_real_transparency(img):
        return img
    if sheet and os.path.isfile(sheet):
        return sheet
    return img if (img and os.path.isfile(img)) else ""


def _load_font(size: int = 14):
    try:
        from PIL import ImageFont
        candidates = [
            "arial.ttf", "Arial.ttf",
            "DejaVuSans.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
        ]
        for fname in candidates:
            try:
                return ImageFont.truetype(fname, size)
            except Exception:
                pass
    except ImportError:
        pass
    return None


def _composite(images_and_names: list[tuple[str, str]], output_path: str) -> bool:
    """
    Creates a labeled grid PNG from (image_path, label) pairs.
    Returns True on success.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return False

    valid = [(p, n) for p, n in images_and_names if p and os.path.isfile(p)]
    if not valid:
        return False

    n          = len(valid)
    cols       = min(n, 3)
    rows       = (n + cols - 1) // cols
    img_area_h = _CELL_H - _LABEL_H

    canvas = Image.new("RGB", (cols * _CELL_W, rows * _CELL_H), _BG)
    draw   = ImageDraw.Draw(canvas)
    font   = _load_font(14)

    for i, (img_path, name) in enumerate(valid):
        col = i % cols
        row = i // cols
        cx  = col * _CELL_W
        cy  = row * _CELL_H

        try:
            img = Image.open(img_path)
            # Détourage (PNG transparent) : composer SUR le fond neutre via le masque
            # alpha. Sans ça, .convert("RGB") laisserait réapparaître les pixels du
            # fond d'origine restés sous l'alpha (bug : « même fond qu'avant détourage »).
            _has_alpha = img.mode in ("RGBA", "LA") or (
                img.mode == "P" and "transparency" in img.info)
            if _has_alpha:
                img = img.convert("RGBA")
                img.thumbnail((_CELL_W - 4, img_area_h - 4))
                px = cx + (_CELL_W - img.width)  // 2
                py = cy + (img_area_h - img.height) // 2
                canvas.paste(img, (px, py), img)   # 3e arg = masque alpha
            else:
                img = img.convert("RGB")
                img.thumbnail((_CELL_W - 4, img_area_h - 4))
                px = cx + (_CELL_W - img.width)  // 2
                py = cy + (img_area_h - img.height) // 2
                canvas.paste(img, (px, py))
        except Exception:
            draw.rectangle(
                [cx + 2, cy + 2, cx + _CELL_W - 3, cy + img_area_h - 3],
                fill=_PLACEHOLDER,
            )

        label_y = cy + img_area_h
        draw.rectangle([cx, label_y, cx + _CELL_W - 1, cy + _CELL_H - 1], fill=_BAR_BG)

        label = name if len(name) <= 24 else name[:23] + "…"
        tx = cx + _CELL_W // 2
        ty = label_y + _LABEL_H // 2
        if font:
            draw.text((tx, ty), label, fill=_TEXT, font=font, anchor="mm")
        else:
            draw.text((cx + 6, label_y + 8), label, fill=_TEXT)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    canvas.save(output_path, "PNG")
    return True


def build_ref_mosaics(
    char_data_map:     dict,
    decor_image_path:  str,
    items_meta:        dict,
    selected_items:    set,
    vehicles_meta:     dict,
    selected_vehicles: set,
    output_dir:        str = "",
) -> tuple[list[str], list[str]]:
    """
    Returns (paths, roles) — parallel lists of up to 3 reference image paths
    and their semantic role ("character", "decor", "accessory").
    Composite mosaics are created in output_dir (temp dir if not specified).
    Falls back to individual images when Pillow is unavailable.
    """
    import tempfile
    if not output_dir:
        output_dir = os.path.join(tempfile.gettempdir(), "seedance_refs")

    ts      = int(time.time())
    results: list[str]  = []
    roles:   list[str]  = []

    # ── Slot 0 : Characters ───────────────────────────────────────────────────
    char_cells = []
    for char in char_data_map.values():
        p = _pick_char_ref(char)   # détourage prioritaire sur la planche (fond d'origine)
        if p and os.path.isfile(p):
            char_cells.append((p, char.get("name", "?")))

    if char_cells:
        out = os.path.join(output_dir, f"ref_chars_{ts}.png")
        if _composite(char_cells, out):
            results.append(out)
        else:
            results.append(char_cells[0][0])  # PIL unavailable — use first image
        roles.append("character")

    # ── Slot 1 : Decor (pass-through) ─────────────────────────────────────────
    if decor_image_path and os.path.isfile(decor_image_path) and len(results) < 3:
        results.append(decor_image_path)
        roles.append("decor")

    # ── Slot 2 : Accessories / HMC / Vehicles ─────────────────────────────────
    other_cells = []
    for iid in selected_items:
        meta = items_meta.get(iid, {})
        p    = meta.get("image_path", "")
        if p and os.path.isfile(p):
            other_cells.append((p, meta.get("name", "?")))
    for vid in selected_vehicles:
        meta = vehicles_meta.get(vid, {})
        p    = meta.get("image_path", "")
        if p and os.path.isfile(p):
            other_cells.append((p, meta.get("name", "?")))

    if other_cells and len(results) < 3:
        out = os.path.join(output_dir, f"ref_others_{ts}.png")
        if _composite(other_cells, out):
            results.append(out)
        else:
            results.append(other_cells[0][0])
        roles.append("accessory")

    return results, roles
