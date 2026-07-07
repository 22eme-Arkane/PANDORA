"""
core/live_building.py — Référence visuelle du BÂTIMENT / FAÇADE pour PANDORA | Live.

Une seule image par projet : la façade sur laquelle le mapping est projeté. Elle est
choisie dans le Conducteur (section « Référence bâtiment ») et réutilisée par la
génération des moods en mode Mapping (Flux Kontext : édite la façade en gardant sa
géométrie). Persistée dans le dossier de données du projet courant.
"""

import os
import json


def _path() -> str:
    from core.context import get_data_root
    return os.path.join(get_data_root(), "live_building_ref.json")


def get_building_ref() -> str:
    """Chemin de l'image de façade du projet courant (vide si aucune)."""
    try:
        with open(_path(), encoding="utf-8") as f:
            p = json.load(f).get("path", "")
        return p if p and os.path.isfile(p) else ""
    except Exception:
        return ""


def set_building_ref(path: str) -> None:
    try:
        p = _path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"path": path or ""}, f)
    except Exception:
        pass


def clear_building_ref() -> None:
    set_building_ref("")


def _desc_cache_path() -> str:
    from core.context import get_data_root
    return os.path.join(get_data_root(), "facade_desc.json")


def describe_facade(image_path: str = "", *, cache: bool = True) -> str:
    """Description TEXTE de la façade RÉELLE (silhouette, étages, fenêtres, portes,
    matériaux) via Claude Haiku Vision — à INJECTER dans les prompts système du mode
    mapping pour que l'IA respecte le bâtiment réel au lieu d'INVENTER des ouvertures.

    Renvoie "" si pas de façade, pas de clé Anthropic, ou erreur (jamais bloquant).
    Mise en cache (facade_desc.json, clé chemin+mtime) pour ne pas rappeler l'IA à
    chaque mise en page / découpage / tour de chat."""
    path = (image_path or "").strip() or get_building_ref()
    if not path or not os.path.isfile(path):
        return ""
    try:
        mtime = os.path.getmtime(path)
    except Exception:
        mtime = 0
    if cache:
        try:
            with open(_desc_cache_path(), encoding="utf-8") as f:
                c = json.load(f)
            if c.get("path") == path and c.get("mtime") == mtime and c.get("desc"):
                return c["desc"]
        except Exception:
            pass
    try:
        from core.config import load_config
        key = load_config().get("anthropic_key", "").strip()
    except Exception:
        key = ""
    if not key:
        return ""
    try:
        import anthropic as _anthropic
        from core.i18n import get_lang
        from core.image_payload import encode_image_for_vision
        # Redimensionne/compresse : une photo de façade pleine résolution dépasse la
        # limite 10 Mo de Claude → ≤1568 px JPEG, largement sous la limite.
        _mime, b64 = encode_image_for_vision(path)
        if get_lang() == "en":
            q = ("This is the FACADE of a real building used for projection mapping. "
                 "Describe ONLY what is actually visible on this frontal photo, factually "
                 "and structured (~6-10 short lines): (a) overall silhouette/shape and "
                 "number of floors/levels; (b) windows — count per level, shape, layout "
                 "(regular grid? asymmetric?); (c) doors/entrances — count, position, shape; "
                 "(d) salient architectural features visible (balconies, cornices, columns, "
                 "pediment, roof); (e) materials/texture (stone, brick, render, glass); "
                 "(f) what is NOT visible (sides, back, roof if out of frame). Do NOT guess "
                 "or invent anything out of frame. Output the description only, no preamble.")
        else:
            q = ("Voici la FAÇADE d'un bâtiment réel servant de support à un mapping vidéo. "
                 "Décris UNIQUEMENT ce qui est réellement visible sur cette photo frontale, "
                 "de façon factuelle et structurée (~6-10 lignes courtes) : (a) silhouette / "
                 "forme générale et nombre d'étages/niveaux ; (b) fenêtres — nombre par "
                 "niveau, forme, disposition (grille régulière ? asymétrique ?) ; (c) portes/"
                 "entrées — nombre, position, forme ; (d) éléments architecturaux saillants "
                 "visibles (balcons, corniches, colonnes, fronton, toit) ; (e) matériaux / "
                 "texture (pierre, brique, crépi, verre) ; (f) ce qui N'EST PAS visible "
                 "(côtés, arrière, toit hors champ). Ne devine ni n'invente rien hors champ. "
                 "Donne la description seule, sans préambule.")
        client = _anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-haiku-4-5", max_tokens=400,
            messages=[{"role": "user", "content": [
                {"type": "image",
                 "source": {"type": "base64", "media_type": _mime, "data": b64}},
                {"type": "text", "text": q}]}])
        desc = msg.content[0].text.strip()
        if desc and cache:
            try:
                p = _desc_cache_path()
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8") as f:
                    json.dump({"path": path, "mtime": mtime, "desc": desc}, f)
            except Exception:
                pass
        return desc
    except Exception:
        return ""


def facade_context_block(desc: str, lang: str = "fr") -> str:
    """Enrobe une description de façade avec la CONSIGNE stricte à injecter dans un
    prompt système de mapping (respect du bâtiment réel, interdiction d'inventer).
    Renvoie "" si la description est vide."""
    desc = (desc or "").strip()
    if not desc:
        return ""
    if lang == "en":
        return ("\n\nREAL REFERENCE FACADE (respect it STRICTLY — the projection is "
                "mapped onto THIS building; do NOT invent windows, doors, floors or any "
                "openings that are not described below):\n" + desc + "\n")
    return ("\n\nFAÇADE RÉELLE DE RÉFÉRENCE (respecte-la STRICTEMENT — le mapping est "
            "projeté sur CE bâtiment ; N'INVENTE PAS de fenêtres, portes, étages ni "
            "ouvertures qui ne sont pas décrits ci-dessous) :\n" + desc + "\n")
