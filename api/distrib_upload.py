"""
api/distrib_upload.py — Envoi des fichiers LOCAUX aux distributeurs vidéo.

Constat Matthieu du 04/10/2026 : en mono-distributeur PiAPI, avec « Se référer
au mood » coché, le mood n'est jamais parti. PANDORA déposait TOUJOURS les
fichiers sur le stockage fal.ai, et le compte fal était bloqué (« User is
locked. Reason: Exhausted balance »). Le plan a été généré SANS le mood… et
facturé ; le bandeau accusait la clé fal, qui était bonne.

Désormais chaque distributeur reçoit les fichiers par SON canal :
  · BytePlus : images et sons en base64 DANS la requête (data URI, 30 Mo) ;
               une vidéo exige une URL publique → relais fal.
  · Runware  : images en data URI dans la requête ; vidéo / son → relais fal.
  · PiAPI    : URL publique obligatoire → dépôt éphémère PiAPI (10 Mo, 24 h,
               abonnement Creator ou plus), sinon relais fal.
  · fal      : stockage fal (géré par api/real.py, inchangé).
Un échec lève UploadError avec la raison RÉELLE de chaque canal essayé ;
api/real.py arrête alors tout AVANT de lancer la génération : rien n'est
généré, rien n'est facturé.
"""
from __future__ import annotations

import base64
import io
import mimetypes
import os

import requests

_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
_VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v", ".mkv", ".avi"}
_AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"}

#: Au-delà, une image est réencodée en JPEG avant d'être intégrée à la requête
#: (une planche PNG de 12 Mo deviendrait 16 Mo de base64 dans le corps JSON).
_INLINE_IMAGE_MAX = 8 * 1024 * 1024
_PIAPI_MAX = 10 * 1024 * 1024
_PIAPI_UPLOAD = "https://upload.theapi.app/api/ephemeral_resource"

#: Le refus « your plan not allowed to upload » ne change pas d'un fichier à
#: l'autre : on ne le redemande pas à chaque image de la session.
_PIAPI_PLAN_REFUSED: list[str] = []


class UploadError(RuntimeError):
    """Un fichier n'a pu être transmis par AUCUN canal du distributeur."""


def media_kind(path: str) -> str:
    ext = os.path.splitext(path or "")[1].lower()
    if ext in _VIDEO_EXT:
        return "video"
    if ext in _AUDIO_EXT:
        return "audio"
    return "image"


def _image_payload(path: str, max_bytes: int) -> tuple[bytes, str, str]:
    """(octets, type MIME, extension) d'une image prête à l'envoi : telle quelle
    si le format est accepté partout et le poids raisonnable, sinon réencodée
    en JPEG (fond blanc sous la transparence, côté long ≤ 4096 px)."""
    ext = os.path.splitext(path)[1].lower()
    size = os.path.getsize(path)
    if ext in _IMAGE_EXT and size <= max_bytes:
        with open(path, "rb") as f:
            data = f.read()
        mime = "image/jpeg" if ext in (".jpg", ".jpeg") else f"image/{ext[1:]}"
        return data, mime, ext
    from PIL import Image
    with Image.open(path) as im:
        im.load()
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
        if max(im.size) > 4096:
            im.thumbnail((4096, 4096))
        for quality in (92, 85, 75):
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=quality)
            if buf.tell() <= max_bytes:
                return buf.getvalue(), "image/jpeg", ".jpg"
    raise UploadError(f"image trop lourde même réencodée ({size // (1024 * 1024)} Mo)")


def data_uri(path: str, max_bytes: int = _INLINE_IMAGE_MAX) -> str:
    """Fichier → data URI base64 (images réencodées si besoin, sons tels quels)."""
    if media_kind(path) == "image":
        data, mime, _ext = _image_payload(path, max_bytes)
    else:
        with open(path, "rb") as f:
            data = f.read()
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def fal_relay_message(err: str) -> str:
    """Raison lisible d'un échec du relais fal (le stockage fal sert d'hôte
    public aux distributeurs qui n'acceptent que des URL)."""
    low = (err or "").lower()
    if "exhausted balance" in low or "user is locked" in low:
        return ("relais fal.ai bloqué : solde fal épuisé (le dépôt y est gratuit mais "
                "exige un compte débloqué — quelques dollars suffisent)")
    if "401" in low or "unauthorized" in low or ("missing" in low and "credential" in low):
        return "relais fal.ai impossible : clé fal.ai absente ou refusée"
    return f"relais fal.ai en échec ({(err or '').strip()[:160]})"


def piapi_upload(path: str, api_key: str) -> str:
    """Dépôt éphémère PiAPI → URL publique (24 h). Lève UploadError."""
    if _PIAPI_PLAN_REFUSED:
        raise UploadError(_PIAPI_PLAN_REFUSED[0])
    kind = media_kind(path)
    name = os.path.basename(path)
    if kind == "image":
        data, _mime, ext = _image_payload(path, _PIAPI_MAX)
        name = os.path.splitext(name)[0] + ext
    else:
        ext = os.path.splitext(path)[1].lower()
        if (kind == "video" and ext != ".mp4") or (kind == "audio" and ext not in (".wav", ".mp3")):
            raise UploadError(f"le dépôt PiAPI n'accepte pas le format {ext or '?'}")
        if os.path.getsize(path) > _PIAPI_MAX:
            raise UploadError("le dépôt PiAPI est limité à 10 Mo par fichier")
        with open(path, "rb") as f:
            data = f.read()
    # Nom ASCII (le champ est limité à 128 caractères, extension obligatoire).
    safe = "".join(c if c.isascii() and (c.isalnum() or c in "._-") else "_" for c in name)
    safe = safe[-120:] or f"pandora{ext}"
    try:
        r = requests.post(_PIAPI_UPLOAD,
                          headers={"x-api-key": api_key.strip(),
                                   "Content-Type": "application/json"},
                          json={"file_name": safe,
                                "file_data": base64.b64encode(data).decode("ascii")},
                          timeout=120)
    except requests.RequestException as e:
        raise UploadError(f"dépôt PiAPI injoignable ({e})")
    try:
        body = r.json() or {}
    except ValueError:
        body = {}
    url = ((body.get("data") or {}).get("url") or "") if isinstance(body, dict) else ""
    if r.status_code < 400 and url:
        return url
    msg = (body.get("message") if isinstance(body, dict) else "") or r.text[:160]
    if r.status_code == 403 and "plan" in (msg or "").lower():
        reason = ("dépôt PiAPI refusé par ton abonnement (« " + msg.strip() + " ») : "
                  "il est réservé à l'abonnement Creator ou plus")
        _PIAPI_PLAN_REFUSED[:] = [reason]
        raise UploadError(reason)
    raise UploadError(f"dépôt PiAPI refusé ({r.status_code}) : {msg}")


class Uploader:
    """Envoie un fichier local à un distributeur ALTERNATIF ; rend une URL
    publique ou un data URI à placer dans la requête du distributeur."""

    def __init__(self, provider: str, api_key: str, fal_relay=None):
        self.provider = provider
        self.api_key = api_key or ""
        self._fal_relay = fal_relay

    def _relay(self, path: str) -> str:
        if self._fal_relay is None:
            raise UploadError("pas de clé fal.ai pour servir de relais")
        try:
            url = self._fal_relay(path)
        except Exception as e:
            raise UploadError(fal_relay_message(str(e)))
        if not url:
            raise UploadError("relais fal.ai : aucune URL rendue")
        return url

    def _channels(self, kind: str):
        if self.provider == "byteplus":
            if kind == "video":
                return (self._relay,)
            return (lambda p: data_uri(p, 30 * 1024 * 1024 if kind == "audio"
                                      else _INLINE_IMAGE_MAX),)
        if self.provider == "runware":
            if kind == "image":
                return (data_uri,)
            return (self._relay,)
        if self.provider == "piapi":
            return (lambda p: piapi_upload(p, self.api_key), self._relay)
        return (self._relay,)

    def send(self, path: str) -> str:
        kind = media_kind(path)
        reasons: list[str] = []
        for channel in self._channels(kind):
            try:
                return channel(path)
            except UploadError as e:
                reasons.append(str(e))
            except OSError as e:
                reasons.append(f"lecture impossible ({e})")
        from core.media_provider import provider_short
        what = {"image": "l'image", "video": "la vidéo", "audio": "le son"}[kind]
        raise UploadError(f"{provider_short(self.provider)} n'a pas pu recevoir {what} "
                          f"« {os.path.basename(path)} » : " + " ; ".join(reasons) + ".")
