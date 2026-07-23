"""Contexte visuel canonique d'un plan Cinéma.

Les fiches persistées (casting, décors, accessoires, HMC, véhicules), le style du
projet et les champs caméra restent les sources de vérité. Ce module relie ces données
au plan sans réécrire l'action, puis produit la bible textuelle remise au compilateur
Seedance au moment de l'envoi.
"""

from __future__ import annotations

import json
import re
import unicodedata


CONTEXT_VERSION = 1


def _norm(value) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _mentioned(name: str, text: str) -> bool:
    needle = _norm(name)
    hay = f" {_norm(text)} "
    return len(needle) >= 2 and f" {needle} " in hay


def load_catalogs() -> dict[str, list[dict]]:
    """Charge les catalogues du projet courant. Aucune écriture."""
    from core.casting import list_characters
    from core.decors import list_decors
    from core.accessories import list_accessories
    from core.hmc import list_hmc_items
    from core.vehicles import list_vehicles
    return {
        "characters": list_characters(),
        "decors": list_decors(),
        "accessories": list_accessories(),
        "hmc": list_hmc_items(),
        "vehicles": list_vehicles(),
    }


def _resolve_many(shot: dict, items: list[dict], id_key: str, name_key: str,
                  search_text: str) -> None:
    by_id = {str(x.get("id")): x for x in items if x.get("id")}
    by_name = {_norm(x.get("name")): x for x in items if x.get("name")}
    ids = [str(x) for x in (shot.get(id_key) or []) if str(x) in by_id]
    explicit_names = [str(x) for x in (shot.get(name_key) or []) if str(x).strip()]
    for name in explicit_names:
        item = by_name.get(_norm(name))
        if item and str(item.get("id")) not in ids:
            ids.append(str(item["id"]))
    for item in items:
        iid, name = str(item.get("id") or ""), str(item.get("name") or "")
        if iid and iid not in ids and _mentioned(name, search_text):
            ids.append(iid)
    shot[id_key] = ids
    shot[name_key] = [str(by_id[i].get("name") or "") for i in ids if i in by_id]


def enrich_shot_entities(shot: dict, catalogs: dict[str, list[dict]] | None = None) -> dict:
    """Complète IDs et noms depuis le texte du plan, sans supprimer une liaison valide."""
    catalogs = catalogs or load_catalogs()
    search = " ".join(str(shot.get(k) or "") for k in (
        "scene_title", "seedance_prompt", "decor_name"))
    _resolve_many(shot, catalogs.get("characters", []),
                  "character_ids", "character_names", search)
    _resolve_many(shot, catalogs.get("accessories", []),
                  "accessory_ids", "accessory_names", search)
    _resolve_many(shot, catalogs.get("vehicles", []),
                  "vehicle_ids", "vehicle_names", search)

    decors = catalogs.get("decors", [])
    by_id = {str(x.get("id")): x for x in decors if x.get("id")}
    by_name = {_norm(x.get("name")): x for x in decors if x.get("name")}
    decor = by_id.get(str(shot.get("decor_id") or ""))
    if decor is None and shot.get("decor_name"):
        decor = by_name.get(_norm(shot["decor_name"]))
    if decor is None:
        decor = next((x for x in decors if _mentioned(x.get("name", ""), search)), None)
    if decor:
        shot["decor_id"] = str(decor.get("id") or "")
        shot["decor_name"] = str(decor.get("name") or "")
    else:
        shot.setdefault("decor_id", "")
        shot.setdefault("decor_name", "")

    # HMC : liaisons explicites du plan + tenues/maquillage/coiffure des personnages.
    hmc = catalogs.get("hmc", [])
    hmc_ids = [str(x) for x in (shot.get("hmc_ids") or []) if x]
    character_ids = set(shot.get("character_ids") or [])
    chars_by_id = {str(x.get("id")): x for x in catalogs.get("characters", []) if x.get("id")}
    for cid in character_ids:
        for hid in chars_by_id.get(str(cid), {}).get("hmc_ids", []) or []:
            if str(hid) not in hmc_ids:
                hmc_ids.append(str(hid))
    for item in hmc:
        iid = str(item.get("id") or "")
        assigned = {str(x) for x in (item.get("assigned_to") or [])}
        if iid and (assigned & character_ids or _mentioned(item.get("name", ""), search)):
            if iid not in hmc_ids:
                hmc_ids.append(iid)
    hmc_by_id = {str(x.get("id")): x for x in hmc if x.get("id")}
    shot["hmc_ids"] = [x for x in hmc_ids if x in hmc_by_id]
    shot["hmc_names"] = [str(hmc_by_id[x].get("name") or "") for x in shot["hmc_ids"]]
    shot["visual_context_version"] = CONTEXT_VERSION
    return shot


_DESC_KEYS = (
    "description", "prompt", "physical_description", "appearance", "morphology",
    "face", "age", "costume", "materials", "material", "colors", "color",
    "distinctive_features", "accessories", "category", "hmc_type", "room_view",
)


def _entity_record(item: dict) -> dict:
    out = {"id": item.get("id", ""), "name": item.get("name", "")}
    # L'image active prime sur le prompt historique. La description canonique n'est
    # utilisée que si son empreinte correspond encore à cette image.
    try:
        from core.visual_identity import canonical_description, identity_matches_image
        identity = item.get("visual_identity") or {}
        image_path = str(item.get("image_path") or "")
        verified = identity_matches_image(identity, image_path)
        canonical = canonical_description(item)
        if canonical:
            out["canonical_description"] = canonical
        out["visual_identity_status"] = (
            "verified" if verified
            else (identity.get("status") or "legacy")
        )
        if identity.get("image_hash"):
            out["visual_identity_hash"] = identity["image_hash"]
    except Exception:
        identity = {}
    for key in _DESC_KEYS:
        # Une identité suivie remplace les anciens champs descriptifs. Tant que
        # l'analyse de la nouvelle image n'est pas prête, mieux vaut n'envoyer
        # aucune description que celle d'une image devenue obsolète.
        if identity and key not in {"category", "hmc_type", "room_view"}:
            continue
        value = item.get(key)
        if value not in (None, "", [], {}):
            out[key] = value
    return out


def build_visual_context(shot: dict, catalogs: dict[str, list[dict]] | None = None) -> dict:
    """Construit la bible visuelle du plan à partir des sources persistées."""
    catalogs = catalogs or load_catalogs()
    shot = enrich_shot_entities(dict(shot or {}), catalogs)
    by_kind = {
        kind: {str(x.get("id")): x for x in items if x.get("id")}
        for kind, items in catalogs.items()
    }

    def _many(kind: str, key: str) -> list[dict]:
        return [_entity_record(by_kind[kind][str(i)]) for i in shot.get(key, [])
                if str(i) in by_kind[kind]]

    decor = by_kind["decors"].get(str(shot.get("decor_id") or ""))
    try:
        from core.style import get_style, get_style_custom, get_video_suffix
        style = get_style() or {}
        style_data = {"key": style.get("key", ""), "name": style.get("name", ""),
                      "description": style.get("description", ""),
                      "video_directives": get_video_suffix(),
                      "custom": get_style_custom()}
    except Exception:
        style_data = {}

    return {
        "version": CONTEXT_VERSION,
        "style": style_data,
        # Bloc narratif (2026-07-23) : l'extrait exact du scénario, le rythme et
        # l'intention du Découpage arrivent enfin jusqu'au composeur de prompt.
        "narrative": {
            "source_excerpt": shot.get("source_excerpt", ""),
            "rhythm":         shot.get("rhythm", ""),
            "intention":      shot.get("intention", ""),
        },
        "continuity": {
            "sequence": shot.get("seq_num", ""), "sequence_name": shot.get("seq_name", ""),
            "shot": shot.get("number", ""), "time": shot.get("shot_time", ""),
        },
        "camera": {k: shot.get(k, "") for k in (
            "shot_size", "camera_movement", "camera_axis", "camera_placement",
            "actor_placement", "focal", "optic", "speed", "duration")},
        "characters": _many("characters", "character_ids"),
        "decor": _entity_record(decor) if decor else None,
        "accessories": _many("accessories", "accessory_ids"),
        "hmc": _many("hmc", "hmc_ids"),
        "vehicles": _many("vehicles", "vehicle_ids"),
    }


def format_visual_context(shot: dict, catalogs: dict[str, list[dict]] | None = None) -> str:
    """JSON lisible et stable transmis au compilateur de prompt, jamais au moteur vidéo."""
    return json.dumps(build_visual_context(shot, catalogs), ensure_ascii=False,
                      indent=2, default=str)


def identity_lock_text(shot: dict, catalogs: dict[str, list[dict]] | None = None) -> str:
    """Résumé humain des identités injectées automatiquement au prompt final."""
    context = build_visual_context(shot, catalogs)
    groups = (
        ("PERSONNAGE", context.get("characters") or []),
        ("DÉCOR", [context.get("decor")] if context.get("decor") else []),
        ("ACCESSOIRE", context.get("accessories") or []),
        ("HMC", context.get("hmc") or []),
        ("VÉHICULE", context.get("vehicles") or []),
    )
    lines = []
    for label, items in groups:
        for item in items:
            desc = str(item.get("canonical_description") or "").strip()
            if not desc:
                continue
            status = item.get("visual_identity_status") or "legacy"
            lines.append(f"{label} · {item.get('name', '')} [{status}] : {desc}")
    return "\n\n".join(lines)
