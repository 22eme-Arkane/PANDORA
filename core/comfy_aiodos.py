"""core/comfy_aiodos.py — Calculer un gabarit ComfyUI sur MES MACHINES, par AIODOS.

Le réglage « Calcul » des gabarits ComfyUI (core/aiodos.compute_mode) a deux
valeurs : « Ce PC » — le ComfyUI local, comme avant (core/comfy_image,
core/comfy_video, api/comfy) — et « Mes machines · AIODOS ». Dans ce cas, le
MÊME graphe API, préparé de la même façon par PANDORA (gabarit, prompt, cadre,
seed, références), part chez AIODOS, qui le fait calculer par le ComfyUI de ce
PC ou d'une de mes machines appairées (chacune l'accorde dans AIODOS, Réglages
→ Moteurs des applications), puis rend les fichiers.

Ce que ce transport change au passage (docs/integrer-aiodos.md § 13, dépôt
d'AIODOS) :
  · les fichiers d'entrée partent par jeton `@in:` — envoyés une fois, par
    empreinte —, jamais par un nom de fichier du serveur ;
  · l'annulation n'arrête QUE ce calcul (le transport local envoie
    /interrupt, qui coupe aussi ce que l'utilisateur fait dans ComfyUI) ;
  · un clip de plus de 100 Mo est refusé AVANT l'envoi ;
  · `sensitive=True` (références : fiches, visages, moods) : ce PC et mes
    machines seulement, jamais les amis ni le réseau public.

Reprise après un redémarrage (docs/integrer-aiodos.md § 8) : le `client_ref`
d'un calcul est STABLE — dérivé de la demande (graphe rempli, entrées par
empreinte, lieu, bornes, projet). Relancer le même calcul après avoir fermé
PANDORA rend le même travail : en cours, il est suivi ; fini, ses fichiers sont
rapatriés ; échoué ou annulé, il est oublié puis relancé. L'onglet AIODOS
liste les travaux dont des fichiers n'ont jamais été récupérés (« Récupérer »,
« Oublier », core/aiodos_view).

Après l'envoi, PANDORA dit ce qu'AIODOS a réellement retenu
(`where_effective`, et `where_reason` s'il le donne).

Pas de repli silencieux vers « Ce PC » : AIODOS pas prêt = une erreur qui dit
le geste à faire (core/aiodos.ready_for_comfy).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import time
import uuid

#: Les nœuds qui lisent un fichier et l'entrée qui le nomme : AIODOS exige un
#: jeton @in: dans chacune (forbidden_value sinon) — vérifié AVANT l'envoi.
FILE_INPUTS = {"LoadImage": "image", "LoadImageMask": "image", "LoadVideo": "file",
               "LoadAudio": "audio"}
#: Bornes d'une unité. `wait_s` : sans machine libre au bout d'une demi-heure,
#: l'unité échoue (« no_machine ») au lieu d'attendre un jour (défaut d'AIODOS).
BOUNDS = {
    "image": {"wait_s": 1800},
    "video": {"wait_s": 1800, "unit_seconds": 4 * 3600, "output_mb": 2048},
}
#: Les résultats attendent ici que PANDORA les range (dossier temporaire du
#: système, purgé au-delà de deux jours) ; une vidéo du Studio va directement
#: dans le dossier de sortie (`dest_dir`).
_KEEP_S = 2 * 24 * 3600
CANCELLED = "Génération annulée."
#: Un travail du même calcul, retrouvé fini sans rien à rapatrier : à relancer.
_REDO = ("failed", "cancelled")

#: Envois en cours (entrées puis dépôt du travail) : le panneau des machines du
#: Studio ne relit rien pendant ce temps (120 requêtes par minute et par appli).
_SENDING = {"n": 0}
_SENDING_LOCK = threading.Lock()


def sending() -> bool:
    """Un envoi vers AIODOS est-il en cours (entrées, dépôt du travail) ?"""
    return _SENDING["n"] > 0


def _sending(delta: int) -> None:
    with _SENDING_LOCK:
        _SENDING["n"] = max(0, _SENDING["n"] + delta)


def _digest(value) -> str:
    """L'empreinte d'une entrée : octets, chemin, ou {"sha256": …}."""
    if isinstance(value, dict):
        return str(value.get("sha256") or "")
    if isinstance(value, (bytes, bytearray, memoryview)):
        return hashlib.sha256(bytes(value)).hexdigest()
    digest = hashlib.sha256()
    with open(value, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def client_ref_for(kind: str, graph: dict, inputs: dict | None = None, *, where=None,
                   sensitive: bool = False, bounds: dict | None = None,
                   project: str | None = None) -> str:
    """Le `client_ref` d'un calcul : le MÊME pour la même demande, d'un lancement
    de PANDORA à l'autre — le graphe rempli (prompt, seed, cadre…), les entrées
    par empreinte, le lieu, les bornes et le projet. Une seed tirée au hasard
    donne donc un autre calcul ; « Reprendre un plan » (même prompt, même seed)
    retrouve le sien. AIODOS rend le même travail pour le même `client_ref`."""
    if project is None:
        try:
            from core.context import get_project_id
            project = get_project_id() or ""
        except Exception:
            project = ""
    payload = {"v": 1, "kind": kind, "project": str(project or ""), "graph": graph,
               "inputs": {str(k): _digest(v) for k, v in sorted((inputs or {}).items())},
               "where": sorted(str(c) for c in where) if where else None,
               "sensitive": bool(sensitive), "bounds": bounds or None}
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                     default=str)
    return f"pandora:{kind}:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:40]}"


def where_note(job, mode: str | None = None, sensitive: bool = False) -> str:
    """Ce qu'AIODOS a réellement retenu pour un travail : « AIODOS — calcul sur :
    ce PC + mes machines », avec sa raison (`where_reason`) s'il la donne. En
    « Réseau public » sans le public retenu, et sans raison donnée, PANDORA le dit."""
    from core import aiodos as _ad
    from core.i18n import translate as _t
    eff = [str(c) for c in getattr(job, "where_effective", ()) or ()]
    if not eff:
        return ""
    text = _t("AIODOS — calcul sur : {places}").format(places=_ad.places_text(eff))
    reason = str(getattr(job, "where_reason", "") or "").strip()
    if reason:
        text += f" ({reason.rstrip('.')})"
    elif sensitive and (mode or _ad.compute_mode()) == _ad.COMPUTE_PUBLIC:
        text += " — " + _t("une référence ou un clip reste sur vos machines")
    elif (mode or _ad.compute_mode()) == _ad.COMPUTE_PUBLIC and "public" not in eff:
        text += " — " + _t("le réseau public ne calcule pas encore les gabarits ComfyUI")
    return text


def _forget_quietly(job, files: bool = True) -> bool:
    try:
        return bool(job.delete(files=files))
    except Exception:
        return False


def _drop_cancelled(job) -> None:
    """Après une annulation demandée par PANDORA : le travail oublié dans AIODOS
    avec ses fichiers déjà rendus (personne ne les récupérerait), s'il est déjà
    fini ; sinon l'onglet AIODOS le montre (« Oublier »)."""
    if job is None:
        return
    try:
        job.refresh()
        if job.finished:
            job.delete(files=True)
    except Exception:
        pass


def enabled() -> bool:
    """Le réglage « Calcul » passe-t-il par AIODOS (mes machines ou réseau public) ?"""
    from core import aiodos
    return aiodos.uses_aiodos()


def require_ready() -> None:
    """AIODOS prêt à calculer un gabarit, sinon RuntimeError avec le geste à
    faire — appelé AVANT de préparer le graphe (lecture du gabarit, des
    références) : l'erreur arrive tout de suite, et rien ne part ailleurs."""
    from core import aiodos
    ok, why = aiodos.ready_for_comfy()
    if not ok:
        raise RuntimeError(why)


def has_saved_definitions() -> bool:
    """PANDORA garde-t-il de quoi préparer un gabarit sans le ComfyUI de ce PC
    (la dernière copie de ses définitions de nœuds, core/comfy_image) ?"""
    try:
        from core.comfy_image import _object_info_path
        return os.path.isfile(_object_info_path())
    except Exception:
        return False


def results_root() -> str:
    return os.path.join(tempfile.gettempdir(), "PANDORA-aiodos")


def _purge(root: str) -> None:
    try:
        now = time.time()
        for name in os.listdir(root):
            path = os.path.join(root, name)
            if os.path.isdir(path) and now - os.path.getmtime(path) > _KEEP_S:
                shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass


def _results_dir(job_id: str) -> str:
    root = results_root()
    os.makedirs(root, exist_ok=True)
    _purge(root)
    return os.path.join(root, re.sub(r"[^A-Za-z0-9_.-]", "_", job_id) or "job")


def unfed_loaders(graph: dict) -> list[tuple[str, str]]:
    """Les nœuds de lecture de fichier restés sans jeton @in: — (id, classe)."""
    out = []
    for nid, node in (graph or {}).items():
        field = FILE_INPUTS.get((node or {}).get("class_type"))
        if field and not str((node.get("inputs") or {}).get(field) or "").startswith("@in:"):
            out.append((str(nid), node["class_type"]))
    return out


def _failure(job) -> str:
    """Le message d'un travail dont aucune unité n'a abouti : l'erreur de
    ComfyUI, et la machine qui l'a rendue."""
    from core.i18n import translate as _t
    failed = [u for u in job.units if u.status == "failed" and isinstance(u.error, dict)]
    codes = {str(u.error.get("code") or "") for u in failed}
    if failed and codes <= {"no_machine"}:
        return _t("AIODOS — aucune machine n'a pris le calcul à temps : ouvrez ComfyUI sur ce PC "
                  "ou sur une de vos machines (et accordez-le dans AIODOS, Réglages → Moteurs "
                  "des applications), puis relancez.")
    unit = next((u for u in failed if u.error.get("message")), None)
    reason = (unit.error.get("message") if unit else None) or (job.error or {}).get("message") \
        or _t("aucune unité n'a pu se faire.")
    where = f"AIODOS · {unit.machine}" if unit is not None and unit.machine else "AIODOS"
    return _t("Échec côté ComfyUI ({where}) : {reason}").format(where=where, reason=reason)


def run(api: dict, files: dict | None = None, *, kind: str = "image", label: str = "PANDORA",
        sensitive: bool = False, progress=None, is_cancelled=None, dest_dir: str | None = None,
        stem: str | None = None) -> list[dict]:
    """Calcule un graphe API DÉJÀ rempli et élagué sur mes machines.

    `files` : {id de nœud de lecture: octets ou chemin} — l'image ou le clip
    que ce nœud doit lire ; `progress(pourcent | None, message)`.
    Rend [{"path", "type", "machine", "place", "node"}], dans l'ordre des
    fichiers du travail. Lève RuntimeError (message pour l'utilisateur)."""
    from aiodos_client import errors as _err
    from core import aiodos as _ad
    from core.i18n import translate as _t

    def say(pct, msg):
        if progress:
            try:
                progress(pct, msg)
            except Exception:
                pass

    ok, why = _ad.ready_for_comfy()
    if not ok:
        raise RuntimeError(why)
    ai = _ad.client()
    mode = _ad.compute_mode()
    where = _ad.job_where(mode)
    bounds = BOUNDS.get(kind) or BOUNDS["image"]
    job = None
    try:
        graph, inputs = ai.comfy.tokenize(api, files) if files else (api, {})
        unfed = unfed_loaders(graph)
        if unfed:
            nid, cls = unfed[0]
            raise RuntimeError(_t("Ce gabarit attend un fichier d'entrée (nœud {node} « {cls} ») "
                                  "que PANDORA ne lui donne pas : ajoutez une image de référence, "
                                  "ou choisissez un autre gabarit.").format(node=nid, cls=cls))
        ref = client_ref_for(kind, graph, inputs, where=where, sensitive=sensitive, bounds=bounds)
        say(4, _t("AIODOS — envoi du travail…"))
        sent_at = time.time()

        def submit(client_ref):
            return ai.comfy.submit(graph=graph, inputs=inputs or None, label=str(label)[:200],
                                   client_ref=client_ref, where=where, sensitive=sensitive,
                                   bounds=bounds, cancel=is_cancelled)
        _sending(+1)
        try:
            job = submit(ref)
            # Le même calcul, déjà déposé (PANDORA fermé pendant le calcul, ou
            # relancé à l'identique) : AIODOS rend le même travail.
            if job.status == "cancelling":
                job.wait(timeout=60, cancel=is_cancelled)
            if job.status in _REDO or (job.status == "completed" and not job.files):
                # Échoué, annulé, ou plus rien à rapatrier : oublié, puis relancé.
                _forget_quietly(job)
                old = job.id
                job = submit(ref)
                if job.id == old:                 # pas oublié : un autre client_ref
                    job = submit(f"{ref}:{uuid.uuid4().hex[:8]}")
            elif job.status in ("paused", "pausing"):
                try:
                    job.resume()                  # en pause dans l'onglet AIODOS : on le reprend
                except _err.AiodosError:
                    pass
        finally:
            _sending(-1)
        if job.created_at and job.created_at < sent_at - 2:
            say(5, _t("AIODOS — ce calcul était déjà lancé : PANDORA le reprend."))
        if mode == _ad.COMPUTE_PUBLIC and not sensitive:
            _ad.note_where_effective(job.where_effective)
        where_msg = where_note(job, mode, sensitive)
        if where_msg:
            say(6, where_msg)
        for ev in job.watch(cancel=is_cancelled):
            if ev.kind == "job":
                p = ev.job.progress
                say(p.percent, f"AIODOS — {p.message}" if p.message
                    else _t("AIODOS — calcul en cours…"))
            elif ev.kind == "unreachable":
                say(None, _t("AIODOS ne répond plus — nouvel essai…"))
        if job.status == "cancelled":
            raise RuntimeError(CANCELLED)
        if job.status == "failed":
            raise RuntimeError(_failure(job))
        say(96, _t("AIODOS — rapatriement des fichiers…"))
        # Un dossier par rapatriement : deux suivis du même travail ne s'y croisent pas.
        paths = job.download(dest_dir or _results_dir(f"{job.id}_{uuid.uuid4().hex[:6]}"),
                             stem=stem, cancel=is_cancelled)
    except _err.Cancelled:
        _drop_cancelled(job)
        raise RuntimeError(CANCELLED) from None
    except _err.AiodosError as e:
        raise RuntimeError(_ad.humanize(e)) from None
    eff = list(job.where_effective or ())
    out = [{"path": str(p), "type": f.type or "", "machine": f.machine or "",
            "place": f.place or "", "node": f.node or "", "where_effective": eff,
            "where_reason": job.where_reason or ""}
           for p, f in zip(paths, paths.files)]
    machines = sorted({o["machine"] for o in out if o["machine"]})
    done = (_t("AIODOS ✓ calculé par {machines}").format(machines=", ".join(machines))
            if machines else "AIODOS ✓")
    if mode == _ad.COMPUTE_PUBLIC and not sensitive and "public" not in eff:
        done += " · " + _t("réseau public : pas encore pour ComfyUI")
    say(100, done)
    return out
