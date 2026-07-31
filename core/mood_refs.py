"""core/mood_refs.py — CE QUI PART RÉELLEMENT au moteur d'images, en UNE liste.

Trois lecteurs se faisaient chacun leur idée des « références du plan » :

  · l'ENVOI            — `api.apercu.run_generation_engine` / `run_generation_nb2` ;
  · le COMPOSITEUR     — `api.apercu._ref_roles`, qui dit au moteur ce qu'il reçoit ;
  · l'ENCART           — la rangée « images envoyées » de la fenêtre Mood.

Les deux premiers avaient déjà divergé, en silence : sur le plan 21 de FIGHTER
(« La traversée », Seedream 5.0 Pro), TROIS images partaient au moteur et ZÉRO
lui étaient annoncées. Le compositeur écrivait donc une description autonome et
complète de la scène ; sur un point d'entrée d'ÉDITION, un texte qui décrit tout
l'emporte sur des images dont on n'a rien dit. Résultat : ni le personnage ni le
décor des fiches n'étaient suivis — le moteur rendait un plan photoréaliste alors
que les deux fiches étaient peintes (constat Matthieu 2026-07-31).

Ce module tranche : une seule fonction décide de l'ordre, du contenu, des rôles
et du plafond. L'envoi prend les chemins, le compositeur prend les rôles,
l'encart affiche les vignettes — tous les trois lisent la MÊME liste. Ce qu'on
voit dans la fenêtre est donc, par construction, ce qui part au moteur.

⚠ L'ORDRE est un contrat : le moteur désigne les images par leur position
(« the LAST image is a floor plan »). Toute réorganisation ici doit être
répercutée dans les directives de `api/apercu.py`.
"""

import os

# ── Natures d'image, dans l'ordre où elles partent ───────────────────────────
KIND_FACADE      = "facade"        # mapping seul — canevas géométrique
KIND_CHARACTER   = "character"
KIND_DECOR       = "decor"
KIND_PROP        = "prop"
KIND_VEHICLE     = "vehicle"
KIND_HMC         = "hmc"
KIND_INSPIRATION = "inspiration"
KIND_FLOOR_PLAN  = "floor_plan"

#: Natures qui servent la COHÉRENCE (mêmes personnages, même décor).
CONSISTENCY_KINDS = (KIND_CHARACTER, KIND_DECOR, KIND_PROP, KIND_VEHICLE, KIND_HMC)

#: Plafond d'inspirations en mapping — chaque image pèse face au texte.
DEFAULT_MAX_INSPIRATION_MAPPING = 2

# Libellés d'interface (français ; traduits par core.i18n comme le reste de l'UI).
_FR_LABEL = {
    KIND_FACADE:      "Façade",
    KIND_CHARACTER:   "Personnage",
    KIND_DECOR:       "Décor",
    KIND_PROP:        "Accessoire",
    KIND_VEHICLE:     "Véhicule",
    KIND_HMC:         "HMC",
    KIND_INSPIRATION: "Inspiration",
    KIND_FLOOR_PLAN:  "Plan d'architecte",
}


class MoodRef:
    """Une image jointe : son chemin, sa nature, le nom de sa fiche."""

    __slots__ = ("path", "kind", "name")

    def __init__(self, path: str, kind: str, name: str = ""):
        self.path = path
        self.kind = kind
        self.name = (name or "").strip()

    def kind_label(self) -> str:
        """Nature seule — la partie TRADUISIBLE du libellé. Le nom d'une fiche
        (« Jésus », « Désert - traversée ») est un nom propre : le passer à la
        traduction ne trouverait rien et afficherait la chaîne entière en
        français dans l'interface anglaise."""
        return _FR_LABEL.get(self.kind, self.kind)

    # Libellé court pour l'encart : « Personnage · Jésus ».
    def label(self) -> str:
        base = self.kind_label()
        return f"{base} · {self.name}" if self.name else base

    def role_en(self) -> str:
        """Ce que le COMPOSITEUR doit dire au moteur de cette image précise.

        Nommer la fiche (« the character Jésus ») vaut mieux que « reference 1 » :
        le moteur relie alors l'image au sujet du prompt au lieu de la traiter
        comme une vignette anonyme."""
        _n = f" — « {self.name} »" if self.name else ""
        if self.kind == KIND_FACADE:
            return ("CANEVAS OBLIGATOIRE — la photo de la façade réelle. Sa "
                    "géométrie, son cadrage, son échelle et son point de vue "
                    "sont intouchables ; le contenu se projette DESSUS.")
        if self.kind == KIND_CHARACTER:
            return (f"COHÉRENCE — fiche du personnage{_n}. Garder ce visage, "
                    "cette coiffure, ce costume ET la facture graphique de la "
                    "fiche. Ne JAMAIS recopier sa pose ni son cadrage.")
        if self.kind == KIND_DECOR:
            return (f"COHÉRENCE — fiche du décor{_n}. Garder son architecture, "
                    "ses matières, ses couleurs, sa lumière ET sa facture "
                    "graphique. Ne pas reprendre son cadrage d'ensemble : la "
                    "caméra du plan entre DANS ce décor.")
        if self.kind == KIND_PROP:
            return (f"COHÉRENCE — fiche de l'accessoire{_n}. Le rendre tel "
                    "qu'il est dessiné s'il apparaît dans le plan.")
        if self.kind == KIND_VEHICLE:
            return (f"COHÉRENCE — fiche du véhicule{_n}. Même modèle, même "
                    "usure, même teinte.")
        if self.kind == KIND_HMC:
            return (f"COHÉRENCE — fiche HMC{_n} (habillage, maquillage, "
                    "coiffure). À respecter sur le personnage concerné.")
        if self.kind == KIND_FLOOR_PLAN:
            return ("PLAN D'ARCHITECTE vu de dessus — repère d'agencement "
                    "seulement (murs, portes, meubles). Ne jamais le dessiner "
                    "dans l'image.")
        return ("INSPIRATION ARTISTIQUE seulement — palette, lumière, matière, "
                "motifs. Ne jamais la recopier, ne jamais en faire le sujet.")


def _first_image(item: dict) -> str:
    """Première image exploitable d'une fiche, sur le disque."""
    if not isinstance(item, dict):
        return ""
    cands = [item.get("image_path"), item.get("sheet_path"),
             item.get("portrait_path"), item.get("portrait")]
    for _g in (item.get("generated_images") or [])[:1]:
        cands.append(_g.get("path") if isinstance(_g, dict) else _g)
    for p in cands:
        if p and isinstance(p, str) and os.path.isfile(p):
            return p
    return ""


def _name_of(item: dict) -> str:
    if not isinstance(item, dict):
        return ""
    return (item.get("name") or item.get("title") or "").strip()


def _consistency_refs(shot: dict, opts: dict) -> list:
    """Fiches du plan, dans l'ordre : personnages, décor, accessoires,
    véhicules, HMC. Les erreurs de lecture sont absorbées fiche par fiche —
    une fiche illisible ne doit pas priver le moteur des autres."""
    out = []
    if opts.get("chars", True):
        try:
            from core import casting as _c
            for cid in (shot.get("character_ids") or []):
                it = _c.get_character(cid) or {}
                p = _first_image(it)
                if p:
                    out.append(MoodRef(p, KIND_CHARACTER, _name_of(it)))
        except Exception:
            pass
    if opts.get("decor", True):
        try:
            from core import decors as _d
            did = shot.get("decor_id")
            if did:
                it = _d.get_decor(did) or {}
                p = _first_image(it)
                if p:
                    out.append(MoodRef(p, KIND_DECOR, _name_of(it) or
                                       (shot.get("decor_name") or "")))
        except Exception:
            pass
    for _flag, _ids, _kind, _mod, _get in (
            ("props",    "accessory_ids", KIND_PROP,    "core.accessories", "get_accessory"),
            ("vehicles", "vehicle_ids",   KIND_VEHICLE, "core.vehicles",    "get_vehicle"),
            ("hmc",      "hmc_ids",       KIND_HMC,     "core.hmc",         "get_hmc_item")):
        if not opts.get(_flag, True):
            continue
        try:
            _m = __import__(_mod, fromlist=[_get])
            _fn = getattr(_m, _get)
            for _id in (shot.get(_ids) or []):
                it = _fn(_id) or {}
                p = _first_image(it)
                if p:
                    out.append(MoodRef(p, _kind, _name_of(it)))
        except Exception:
            pass
    return out


def reference_plan(shot: dict, building_ref: str = "", is_mapping=None,
                   options: dict | None = None, inspiration_ref: str = "",
                   max_refs: int | None = None,
                   max_inspiration_mapping: int = DEFAULT_MAX_INSPIRATION_MAPPING) -> list:
    """Liste ORDONNÉE et PLAFONNÉE des images qui partent au moteur.

    Mapping  : façade (canevas) puis inspirations, plafonnées.
    Cinéma   : fiches de cohérence, puis inspirations du plan, puis plan d'architecte.

    `max_refs` (capacité du moteur) tronque en fin de liste — c'est pourquoi le
    plan d'architecte, désigné au moteur comme « la DERNIÈRE image », vient en
    dernier et disparaît le premier."""
    shot = shot or {}
    opts = options or {}
    if is_mapping is None:
        is_mapping = bool(building_ref and os.path.isfile(building_ref))

    _insp = [p for p in (shot.get("reference_images") or [])
             if p and os.path.isfile(p)]
    if inspiration_ref and os.path.isfile(inspiration_ref):
        _insp = [inspiration_ref] + [p for p in _insp if p != inspiration_ref]

    plan = []
    if is_mapping and building_ref and os.path.isfile(building_ref):
        plan.append(MoodRef(building_ref, KIND_FACADE))
        plan += [MoodRef(p, KIND_INSPIRATION) for p in _insp[:max_inspiration_mapping]]
    else:
        plan += _consistency_refs(shot, opts)
        plan += [MoodRef(p, KIND_INSPIRATION) for p in _insp]
        if opts.get("floor_plan", True):
            try:
                from core.decors import floor_plan_for_shot
                _fp = floor_plan_for_shot(shot) or ""
                if _fp and os.path.isfile(_fp):
                    plan.append(MoodRef(_fp, KIND_FLOOR_PLAN))
            except Exception:
                pass

    if max_refs is not None and max_refs >= 0:
        plan = plan[:max_refs]
    return plan


def paths_of(plan: list, kinds=None) -> list:
    """Chemins seuls, éventuellement filtrés par nature."""
    return [r.path for r in plan if (kinds is None or r.kind in kinds)]
