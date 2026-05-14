from davinci.bridge import resolve


def get_selected_clip() -> dict | None:
    """Retourne les infos du clip sélectionné dans la timeline via le bridge, ou None."""
    info = resolve.get_selected_clip_info()
    return info if isinstance(info, dict) and info else None


def get_clip_info(clip) -> dict:
    """Extrait les infos utiles d'un clip (déjà un dict retourné par le bridge)."""
    if isinstance(clip, dict):
        return clip
    return {}
