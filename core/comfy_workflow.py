"""core/comfy_workflow.py — Workflows ComfyUI : lecture, aplatissement, conversion, remplissage.

ComfyUI a DEUX formats de workflow, et c'est la première chose qui surprend :

  - le format **éditeur** (« UI ») : ce que l'on enregistre depuis l'interface
    — `nodes[]` avec leurs `widgets_values` dans l'ordre d'affichage, `links[]`
    qui relient les prises, et depuis la v0.4 des `definitions.subgraphs` ;
  - le format **API** : ce que `POST /prompt` accepte —
    `{"<id>": {"class_type": …, "inputs": {nom: valeur | [id_source, slot]}}}`.

Les gabarits livrés avec ComfyUI et tout ce qu'un utilisateur exporte d'un
clic sont au format éditeur. Exiger le format API reviendrait à demander à
chacun de connaître le menu « Export (API) » : PANDORA convertit lui-même.

SOUS-GRAPHES (gabarits MiniMax H3 officiels, relevé 2026-09-13). Un nœud dont
le `type` est l'identifiant d'un sous-graphe en instancie le contenu :
  - ses `inputs` reprennent, dans l'ordre, les `inputs` du sous-graphe ; ceux
    qui ne sont pas des connexions (STRING, INT, FLOAT, COMBO, BOOLEAN) sont
    des widgets « promus », et leurs valeurs sont les `widgets_values` du nœud
    externe, dans ce même ordre ;
  - dans les liens internes, `origin_id = -10` désigne l'entrée du sous-graphe
    (`origin_slot` = index de l'entrée) et `target_id = -20` sa sortie.
Le frontend aplatit tout cela avant l'envoi, avec des identifiants
« externe:interne » ; on fait exactement pareil.

La conversion a besoin des DÉFINITIONS de nœuds (`GET /object_info`) pour
savoir dans quel ordre les `widgets_values` tombent dans les entrées. Trois
pièges connus, tous traités : une entrée à `control_after_generate` consomme
UNE valeur de plus (« fixed » / « randomize ») ; les nœuds virtuels de
l'éditeur (`Note`, `MarkdownNote`, `PrimitiveNode`, `Reroute`) n'existent pas
côté serveur ; un nœud muet (mode 2) ou contourné (mode 4) ne part pas.

Module PUR : aucune requête ici. `object_info` est passé en paramètre.
"""

from __future__ import annotations

import json
import os

#: Types de prise = connexions, jamais des widgets.
_LINK_TYPES = {"MODEL", "CLIP", "VAE", "LATENT", "IMAGE", "MASK", "CONDITIONING",
               "AUDIO", "VIDEO", "GUIDER", "SAMPLER", "SIGMAS", "NOISE", "CONTROL_NET",
               "CLIP_VISION", "STYLE_MODEL", "UPSCALE_MODEL", "GLIGEN", "PHOTOMAKER"}
_WIDGET_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO"}
_VIRTUAL = ("Note", "MarkdownNote", "PrimitiveNode", "Reroute")
_MODE_MUTED, _MODE_BYPASSED = 2, 4
_SG_IN, _SG_OUT = -10, -20


# ── Lecture ──────────────────────────────────────────────────────────────────

def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_api_format(wf: dict) -> bool:
    """Un dict dont les valeurs portent `class_type` : déjà prêt pour /prompt."""
    if not isinstance(wf, dict) or "nodes" in wf:
        return False
    vals = [v for v in wf.values() if isinstance(v, dict)]
    return bool(vals) and all("class_type" in v for v in vals)


def is_ui_format(wf: dict) -> bool:
    return isinstance(wf, dict) and isinstance(wf.get("nodes"), list)


def _is_link_type(t) -> bool:
    return isinstance(t, str) and (t.upper() in _LINK_TYPES or t == "*")


# ── Liens ────────────────────────────────────────────────────────────────────

def _norm_links(raw) -> dict[str, tuple[str, int, str, int]]:
    """link_id → (origine, slot, cible, slot). Accepte les deux écritures :
    liste `[id, o, os, t, ts, type]` (racine) ou dict (sous-graphes)."""
    out: dict[str, tuple[str, int, str, int]] = {}
    for l in raw or []:
        if isinstance(l, (list, tuple)) and len(l) >= 5:
            out[str(l[0])] = (str(l[1]), int(l[2]), str(l[3]), int(l[4]))
        elif isinstance(l, dict) and "id" in l:
            out[str(l["id"])] = (str(l["origin_id"]), int(l["origin_slot"]),
                                 str(l["target_id"]), int(l["target_slot"]))
    return out


# ── Aplatissement des sous-graphes ───────────────────────────────────────────

def flatten(wf: dict) -> dict:
    """Format éditeur → format éditeur SANS sous-graphes.

    Les nœuds internes reçoivent l'identifiant « externe:interne ». Les entrées
    de frontière deviennent : un lien vers la source externe si le nœud
    externe est branché sur cette prise, sinon un `PrimitiveNode` synthétique
    portant la valeur promue — que le convertisseur sait déjà résoudre. Les
    sorties de frontière redirigent les liens externes vers le nœud interne
    qui les produit. Récursif : un sous-graphe peut en contenir un autre.
    """
    if not is_ui_format(wf):
        return wf
    defs = {str(s.get("id")): s for s in ((wf.get("definitions") or {}).get("subgraphs") or [])}
    nodes = [dict(n) for n in wf.get("nodes", [])]
    links = _norm_links(wf.get("links"))
    if not defs or not any(str(n.get("type")) in defs for n in nodes):
        return {"nodes": nodes, "links": [[k, *v] for k, v in links.items()]}

    out_nodes: list[dict] = []
    new_links: dict[str, tuple[str, int, str, int]] = {}
    next_link = [max([int(k) for k in links if k.lstrip("-").isdigit()] + [0]) + 1]
    # Sorties de frontière : (id externe, slot) → (id interne aplati, slot)
    redirect: dict[tuple[str, int], tuple[str, int]] = {}

    def fresh_link() -> str:
        next_link[0] += 1
        return str(next_link[0])

    for n in nodes:
        sid = str(n.get("type"))
        if sid not in defs:
            out_nodes.append(n)
            continue
        sg = defs[sid]
        outer_id = str(n["id"])
        # Aplatir d'abord l'intérieur (sous-graphes imbriqués).
        inner = flatten({"nodes": sg.get("nodes", []), "links": sg.get("links", []),
                         "definitions": wf.get("definitions")})
        in_nodes = {str(x["id"]): dict(x) for x in inner["nodes"]}
        in_links = _norm_links(inner["links"])
        sg_inputs = sg.get("inputs") or []
        sg_outputs = sg.get("outputs") or []

        # Valeurs promues : widgets_values externes ↔ entrées non-connexion, dans l'ordre.
        promoted = [i for i, spec in enumerate(sg_inputs) if not _is_link_type(spec.get("type"))]
        wv = list(n.get("widgets_values") or [])
        slot_value = {slot: wv[k] for k, slot in enumerate(promoted) if k < len(wv)}
        outer_inputs = n.get("inputs") or []

        def rename(iid: str) -> str:
            return f"{outer_id}:{iid}"

        # Nœuds internes, renommés.
        for iid, x in in_nodes.items():
            x = dict(x)
            x["id"] = rename(iid)
            x["inputs"] = [dict(i) for i in (x.get("inputs") or [])]
            out_nodes.append(x)
            in_nodes[iid] = x

        # Liens internes.
        for lid, (o, os_, t, ts) in in_links.items():
            if o == str(_SG_IN):
                spec = sg_inputs[os_] if os_ < len(sg_inputs) else {}
                # La prise externe correspondante — PAR NOM, jamais par index :
                # le nœud externe ne liste que les prises exposées (9 sur 15
                # dans les gabarits H3), son index 2 est « width », pas « prompt ».
                # Cette confusion reliait le prompt au ResolutionSelector.
                ext = next((x for x in outer_inputs
                            if x.get("name") == spec.get("name")), None)
                if ext is None and not spec.get("name"):
                    ext = outer_inputs[os_] if os_ < len(outer_inputs) else {}
                ext = ext or {}
                target = in_nodes.get(t)
                if target is None:
                    continue
                tin = target["inputs"][ts] if ts < len(target["inputs"]) else None
                if ext.get("link") is not None and str(ext["link"]) in links:
                    src = links[str(ext["link"])]
                    nl = fresh_link()
                    new_links[nl] = (src[0], src[1], rename(t), ts)
                    if tin is not None:
                        tin["link"] = nl
                elif os_ in slot_value or not _is_link_type(spec.get("type")):
                    # Valeur promue → PrimitiveNode synthétique.
                    pid = f"{outer_id}:promoted:{os_}"
                    out_nodes.append({"id": pid, "type": "PrimitiveNode",
                                      "widgets_values": [slot_value.get(os_)],
                                      "inputs": [], "outputs": [{"links": []}]})
                    nl = fresh_link()
                    new_links[nl] = (pid, 0, rename(t), ts)
                    if tin is not None:
                        tin["link"] = nl
                else:
                    # Prise de connexion externe non branchée (first_frame absent) :
                    # l'entrée interne reste libre.
                    if tin is not None:
                        tin["link"] = None
            elif t == str(_SG_OUT):
                redirect[(outer_id, ts)] = (rename(o), os_)
            else:
                nl = fresh_link()
                new_links[nl] = (rename(o), os_, rename(t), ts)
                target = in_nodes.get(t)
                if target is not None and ts < len(target["inputs"]):
                    target["inputs"][ts]["link"] = nl

    # Liens externes : ceux qui partent d'un nœud de sous-graphe sont redirigés.
    for lid, (o, os_, t, ts) in links.items():
        key = (o, os_)
        if key in redirect:
            new_links[lid] = (redirect[key][0], redirect[key][1], t, ts)
        elif str(o) in {str(x["id"]) for x in nodes if str(x.get("type")) in defs}:
            continue
        elif str(t) in {str(x["id"]) for x in nodes if str(x.get("type")) in defs}:
            continue          # consommé par la frontière ci-dessus
        else:
            new_links[lid] = (o, os_, t, ts)

    return {"nodes": out_nodes, "links": [[k, *v] for k, v in new_links.items()]}


# ── Définitions de nœuds ─────────────────────────────────────────────────────

def _widget_inputs(class_def: dict) -> list[tuple[str, bool]]:
    """(nom, consomme_une_valeur_de_contrôle) pour chaque entrée-widget, dans
    l'ordre required puis optional — l'ordre dans lequel l'éditeur range les
    `widgets_values`."""
    out: list[tuple[str, bool]] = []
    spec = (class_def or {}).get("input") or {}
    for section in ("required", "optional"):
        for name, desc in (spec.get(section) or {}).items():
            if not isinstance(desc, (list, tuple)) or not desc:
                continue
            kind = desc[0]
            extra = desc[1] if len(desc) > 1 and isinstance(desc[1], dict) else {}
            if isinstance(kind, list):
                is_widget = True                       # COMBO = liste de choix
            elif isinstance(kind, str):
                is_widget = kind in _WIDGET_TYPES and not _is_link_type(kind)
            else:
                is_widget = False
            if extra.get("forceInput"):
                is_widget = False
            if is_widget:
                out.append((name, bool(extra.get("control_after_generate"))))
    return out


# ── Conversion ───────────────────────────────────────────────────────────────

class ConversionError(ValueError):
    pass


def to_api(wf: dict, object_info: dict) -> dict:
    """Format éditeur → format API. Lève ConversionError avec un message
    lisible quand une classe de nœud est inconnue du serveur (nœud
    personnalisé non installé — la cause n°1 d'un workflow qui ne tourne pas)."""
    if is_api_format(wf):
        return dict(wf)
    if not is_ui_format(wf):
        raise ConversionError("Ce fichier n'est ni un workflow ComfyUI ni un export API.")
    flat = flatten(wf)
    nodes = {str(n["id"]): n for n in flat.get("nodes", []) if "id" in n}
    links = _norm_links(flat.get("links"))

    def source_of(link_id) -> tuple[str, int] | None:
        """Remonte les Reroute jusqu'à une vraie source."""
        seen = 0
        while link_id is not None and seen < 64:
            seen += 1
            src = links.get(str(link_id))
            if not src:
                return None
            n = nodes.get(src[0])
            if n and n.get("type") == "Reroute":
                ins = n.get("inputs") or []
                link_id = ins[0].get("link") if ins else None
                continue
            return src[0], src[1]
        return None

    def primitive_value(link_id):
        src = links.get(str(link_id)) if link_id is not None else None
        if not src:
            return (False, None)
        n = nodes.get(src[0])
        if n and n.get("type") == "PrimitiveNode":
            wv = n.get("widgets_values") or []
            return (True, wv[0] if wv else None)
        return (False, None)

    api: dict = {}
    unknown: list[str] = []
    for nid, n in nodes.items():
        ctype = n.get("type", "")
        if ctype in _VIRTUAL:
            continue
        if n.get("mode") in (_MODE_MUTED, _MODE_BYPASSED):
            continue
        cdef = object_info.get(ctype)
        if cdef is None:
            unknown.append(ctype)
            continue

        inputs: dict = {}
        linked_names: set[str] = set()
        for slot in n.get("inputs") or []:
            name = slot.get("name")
            lid = slot.get("link")
            if lid is None or not name:
                continue
            is_prim, pv = primitive_value(lid)
            if is_prim:
                inputs[name] = pv
                linked_names.add(name)
                continue
            src = source_of(lid)
            if src is None:
                continue
            inputs[name] = [src[0], src[1]]
            linked_names.add(name)

        raw_wv = n.get("widgets_values")
        if isinstance(raw_wv, dict):
            for k, v in raw_wv.items():
                if k not in linked_names:
                    inputs[k] = v
        else:
            values = list(raw_wv or [])
            i = 0
            for name, has_control in _widget_inputs(cdef):
                if name in linked_names:
                    # Le widget converti en prise ne consomme pas de valeur —
                    # sauf s'il porte un contrôle, qui reste dans la liste.
                    if has_control and i < len(values):
                        i += 1
                    continue
                if i < len(values):
                    inputs[name] = values[i]
                    i += 1
                if has_control:
                    i += 1          # « fixed » / « randomize » : pas une entrée
        api[str(nid)] = {"class_type": ctype, "inputs": inputs}

    if unknown:
        raise ConversionError(
            "Nœuds inconnus du serveur : " + ", ".join(sorted(set(unknown)))
            + ". Il manque probablement un nœud personnalisé, ou ComfyUI est "
              "trop ancien pour ce workflow.")
    return api


# ── Remplissage ──────────────────────────────────────────────────────────────

def find(api: dict, class_type: str) -> list[str]:
    """Identifiants des nœuds d'une classe, dans l'ordre du fichier."""
    return [nid for nid, n in api.items() if n.get("class_type") == class_type]


def set_input(api: dict, node_id: str, name: str, value) -> None:
    api[str(node_id)].setdefault("inputs", {})[name] = value


def fill(api: dict, plan: list[tuple[str, str, object]]) -> list[str]:
    """Applique une liste de (classe, entrée, valeur) sur le PREMIER nœud de
    chaque classe. Rend la liste des classes introuvables — l'appelant décide
    si c'est bloquant (pas de nœud de prompt) ou non (pas de seed)."""
    missing: list[str] = []
    for ctype, name, value in plan:
        ids = find(api, ctype)
        if not ids:
            missing.append(ctype)
            continue
        set_input(api, ids[0], name, value)
    return missing


def describe(api: dict) -> str:
    """Résumé lisible d'un workflow API : une ligne par nœud."""
    lines = []
    for nid, n in api.items():
        ins = n.get("inputs") or {}
        widgets = [f"{k}={v!r}" for k, v in ins.items() if not isinstance(v, list)]
        lines.append(f"{nid:>8}  {n.get('class_type', '?'):32} {' '.join(widgets)[:90]}")
    return "\n".join(lines)


def workflows_dir() -> str:
    """Dossier des gabarits livrés avec PANDORA (assets/comfy_workflows)."""
    from core.paths import APP_ROOT
    return os.path.join(APP_ROOT, "assets", "comfy_workflows")
