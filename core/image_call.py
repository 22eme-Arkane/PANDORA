"""core/image_call.py — Un seul point d'appel pour générer une image, fal ou ComfyUI.

Tous les points de génération de PANDORA (fiches, moods, Studio Images)
faisaient `fal_client.subscribe(endpoint, arguments=…)` puis téléchargeaient
l'URL rendue. Ils appellent désormais `subscribe()` d'ici : un endpoint
« comfy:<gabarit> » (core/comfy_catalog) part vers ComfyUI (core/comfy_image),
qui rend la MÊME forme — une URL `/view` du serveur local, téléchargeable
comme une URL fal — et tout le reste (nommage, redimensionnement, journal de
dépenses) reste tel quel. Les autres endpoints vont à fal comme avant.

`needs_fal(engine_key)` : un moteur ComfyUI se passe de clé fal — sans quoi
un utilisateur qui n'a QUE ComfyUI tomberait sur le mode « mock ».
"""

from __future__ import annotations


def is_comfy_endpoint(endpoint: str) -> bool:
    from core.comfy_catalog import PREFIX
    return str(endpoint or "").startswith(PREFIX)


def needs_fal(engine_key: str) -> bool:
    return not is_comfy_endpoint(engine_key)


def subscribe(endpoint: str, arguments: dict | None = None, progress=None,
              is_cancelled=None, **kw) -> dict:
    if is_comfy_endpoint(endpoint):
        from core import comfy_image
        from core.comfy_catalog import template_name
        return comfy_image.subscribe(template_name(endpoint), arguments, progress, is_cancelled)
    import fal_client
    return fal_client.subscribe(endpoint, arguments=arguments or {}, **kw)
