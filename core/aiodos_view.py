"""core/aiodos_view.py — Ce que montrent l'onglet AIODOS et le panneau des machines.

Demande Matthieu (27/10/2026) : « un nouvel onglet AIODOS pour voir les tâches en
cours, les clients qui sont connectés, et quelques réglages », et dans le Studio
IA « un panneau pliable avec les personnes connectées, comme les clients de
BitTorrent ».

L'API des applications d'AIODOS n'a pas (encore) de route « liste des pairs » :
la liste des machines se COMPOSE à partir de ce qu'elle sert —
  · les moteurs (`engines`) : ce PC (ComfyUI accordé, version, mémoire vidéo) et
    les machines appairées qui ont des modèles ComfyUI ;
  · le catalogue de conversation (`models`) : sur quelles machines chaque modèle
    est installé, et chargé ;
  · les travaux de PANDORA (`jobs`) : quelles machines calculent, combien
    d'unités en cours et faites — le « pair » de BitTorrent.

Sans Qt ; bloquant (à appeler depuis un fil). `snapshot()` ne lève jamais : ce
qui n'a pas pu être lu va dans `errors`.

Fichiers jamais récupérés (relecture du 28/10/2026) : dans AIODOS, un fichier
qu'aucune appli n'a récupéré n'est JAMAIS effacé seul ; si PANDORA est fermé
pendant un calcul, ses fichiers restent là jusqu'au quota. Le relevé les compte
(`unfetched`), `fetch()` les range dans PANDORA/AIODOS/ du dossier de sortie,
`forget()` oublie un travail avec ses fichiers jamais récupérés.
"""
from __future__ import annotations

import os
import socket
import time

#: Ordre d'affichage des lieux de calcul.
PLACES = ("here", "mine", "friend", "public")
ACTIVE = ("queued", "in_progress", "pausing", "paused", "cancelling")


def _place(value) -> str:
    v = str(value or "")
    return {"friends": "friend"}.get(v, v) or "mine"


def _machine(machines: dict, name, place) -> dict:
    """La fiche d'une machine (créée à la première mention)."""
    place = _place(place)
    if place == "here":
        # Ce PC : une seule fiche, quel que soit le nom sous lequel on le voit.
        for m in machines.values():
            if m["place"] == "here":
                if name and m["name"] == m.get("_default_name"):
                    m["name"] = str(name)
                return m
        key = "here"
    else:
        key = f"{place}:{name}"
    if key not in machines:
        default = socket.gethostname() if place == "here" else ""
        machines[key] = {"name": str(name or default or "?"), "_default_name": default,
                         "place": place, "comfy": False, "comfy_models": 0,
                         "comfy_version": None, "vram_mib": None, "chat_models": [],
                         "loaded": [], "running": 0, "done": 0, "jobs": 0, "busy": False}
    return machines[key]


def _unfetched(job) -> list:
    """Les fichiers d'un travail qu'aucune appli n'a récupérés (jamais effacés seuls)."""
    return [f for f in (getattr(job, "files", None) or ()) if not getattr(f, "fetched", False)]


def _job_row(job) -> dict:
    p = job.progress
    files = list(job.files or ())
    unfetched = _unfetched(job)
    return {
        "id": job.id, "label": job.label or job.id, "status": job.status or "",
        "percent": p.percent, "message": p.message or "", "total": p.total, "done": p.done,
        "running": p.running, "failed": p.failed, "eta_s": p.eta_s,
        "machines": [{"name": m.name or "?", "place": _place(m.place), "running": m.running,
                      "done": m.done} for m in p.machines],
        "created_at": job.created_at, "finished": job.finished,
        "where_effective": list(job.where_effective or ()), "where_reason": job.where_reason or "",
        "client_ref": job.client_ref or "", "files": len(files), "unfetched": len(unfetched),
        "unfetched_bytes": sum(int(f.bytes or 0) for f in unfetched),
    }


def snapshot(jobs_limit: int = 40) -> dict:
    """L'état d'AIODOS, ses machines et les travaux de PANDORA, prêts à afficher :
    les `jobs_limit` plus récents, plus tout travail plus ancien dont des fichiers
    n'ont jamais été récupérés (`unfetched` : leur total)."""
    from core import aiodos
    out = {"at": time.time(), "state": "not_installed", "message": "", "version": None,
           "ready": False, "where": [], "features": [], "machines": [], "jobs": [],
           "errors": [], "comfy_here": None,
           "unfetched": {"jobs": 0, "files": 0, "bytes": 0}}
    try:
        st = aiodos.status(max_age=0)
    except Exception as e:                       # status() ne lève pas ; par prudence
        out["errors"].append(str(e))
        return out
    out.update(state=st.state, message=st.message or "", version=getattr(st, "version", None),
               ready=st.state == "ready", where=list(getattr(st, "where", ()) or ()),
               features=list(getattr(st, "features", ()) or ()))
    if not out["ready"]:
        return out
    ai = aiodos.client()
    feats = set(out["features"])
    machines: dict = {}

    if "engines" in feats:
        try:
            comfy = ai.engines().by_id.get("comfyui")
        except Exception as e:
            out["errors"].append(aiodos.humanize(e))
            comfy = None
        if comfy is not None:
            here = comfy.here or {}
            out["comfy_here"] = {"enabled": comfy.enabled, "version": here.get("version"),
                                 "vram_mib": here.get("vram_mib")}
            if comfy.enabled:
                m = _machine(machines, None, "here")
                m.update(comfy=True, comfy_version=here.get("version"),
                         vram_mib=here.get("vram_mib"))
            for model in comfy.models:
                where = model.where or {}
                if where.get("here"):
                    _machine(machines, None, "here")["comfy_models"] += 1
                for name in where.get("mine") or ():
                    m = _machine(machines, name, "mine")
                    m["comfy"] = True
                    m["comfy_models"] += 1

    if "models" in feats:
        try:
            for model in ai.models("chat"):
                for p in model.where:
                    m = _machine(machines, p.machine, p.place or ("here" if model.here else "mine"))
                    if model.id not in m["chat_models"]:
                        m["chat_models"].append(model.id)
                    if p.loaded and model.id not in m["loaded"]:
                        m["loaded"].append(model.id)
        except Exception as e:
            out["errors"].append(aiodos.humanize(e))

    if "jobs" in feats:
        try:
            listed = ai.jobs(active=None)            # les plus récents d'abord (200 au plus)
        except Exception as e:
            out["errors"].append(aiodos.humanize(e))
            listed = []
        jobs = listed[:jobs_limit] + [j for j in listed[jobs_limit:] if _unfetched(j)]
        for job in jobs:
            row = _job_row(job)
            out["jobs"].append(row)
            if row["unfetched"]:
                out["unfetched"]["jobs"] += 1
                out["unfetched"]["files"] += row["unfetched"]
                out["unfetched"]["bytes"] += row["unfetched_bytes"]
            for jm in row["machines"]:
                m = _machine(machines, jm["name"], jm["place"])
                m["done"] += int(jm["done"] or 0)
                if row["status"] in ACTIVE:
                    m["running"] += int(jm["running"] or 0)
                    m["jobs"] += 1
                    m["busy"] = m["busy"] or bool(jm["running"])

    rows = []
    for m in machines.values():
        m.pop("_default_name", None)
        rows.append(m)
    rows.sort(key=lambda m: (PLACES.index(m["place"]) if m["place"] in PLACES else 9,
                             m["name"].lower()))
    out["machines"] = rows
    return out


def job_action(job_id: str, action: str):
    """« pause », « resume », « cancel », « retry » ou « delete » (= forget) sur un
    travail de PANDORA. Rend, pour « delete », le nombre de fichiers jamais
    récupérés effacés avec lui. Lève RuntimeError (message pour l'utilisateur)."""
    from aiodos_client import errors as _err
    from core import aiodos
    if action == "delete":
        return forget(job_id)
    try:
        job = aiodos.client().job(job_id)
        if action == "pause":
            job.pause()
        elif action == "resume":
            job.resume()
        elif action == "cancel":
            job.cancel()
        elif action == "retry":
            job.retry_failed()
        else:
            raise ValueError(action)
    except _err.AiodosError as e:
        raise RuntimeError(aiodos.humanize(e)) from None
    return None


def forget(job_id: str) -> int:
    """« Oublier » un travail fini. Ses fichiers jamais récupérés partent AVEC lui
    (`files=True`) : sinon AIODOS les garderait sans fin, jusqu'au quota. Des
    fichiers déjà récupérés suivent leur garde (7 jours). Rend le nombre de
    fichiers jamais récupérés effacés. Lève RuntimeError."""
    from aiodos_client import errors as _err
    from core import aiodos
    try:
        job = aiodos.client().job(job_id)
        unfetched = _unfetched(job)
        job.delete(files=bool(unfetched))
    except _err.AiodosError as e:
        raise RuntimeError(aiodos.humanize(e)) from None
    return len(unfetched)


def fetch(job_id: str, dest_root: str | None = None) -> tuple[str, int]:
    """« Récupérer » les fichiers d'un travail de PANDORA (laissés dans AIODOS,
    par exemple PANDORA fermé pendant le calcul) : rangés dans
    <dossier de sortie>/PANDORA/AIODOS/<travail>/. Rend (dossier, nombre de
    fichiers). Récupérés, AIODOS les garde encore 7 jours puis les efface seul.
    Lève RuntimeError."""
    from aiodos_client import errors as _err
    from aiodos_client.files import safe_name
    from core import aiodos
    from core.i18n import translate as _t
    try:
        job = aiodos.client().job(job_id)
        if not job.files:
            raise RuntimeError(_t("Ce travail n'a aucun fichier à récupérer."))
        if dest_root is None:
            from core.pandora_dirs import get_bin_dir
            dest_root = get_bin_dir("AIODOS")
        label = str(job.label or "")
        if label.startswith("PANDORA · "):
            label = label[len("PANDORA · "):]
        stem = safe_name(label or "aiodos", "aiodos")
        folder = os.path.join(dest_root, safe_name(f"{stem}_{job.id[-8:]}", "aiodos"))
        paths = job.download(folder, stem=stem)
    except _err.AiodosError as e:
        raise RuntimeError(aiodos.humanize(e)) from None
    return folder, len(paths)


def size_text(n: int) -> str:
    """« 640 Mo », « 2,4 Go »."""
    n = int(n or 0)
    if n >= 1_000_000_000:
        return f"{n / 1e9:.1f} Go".replace(".", ",")
    return f"{max(1, round(n / 1e6)) if n else 0} Mo"


def open_aiodos(page: str = "jobs") -> bool:
    """Ramène la fenêtre d'AIODOS (page « jobs », « applications »…)."""
    from core import aiodos
    try:
        return bool(aiodos.client().open_in_aiodos(page))
    except Exception:
        return False


def summary(snap: dict) -> str:
    """« 3 machines · 1 travail en cours » (pour les en-têtes repliés)."""
    from core.i18n import translate as _t
    if not snap or not snap.get("ready"):
        return _t("non connecté")
    n = len(snap.get("machines") or ())
    active = sum(1 for j in snap.get("jobs") or () if j.get("status") in ACTIVE)
    parts = [_t("{n} machine(s)").format(n=n)]
    if active:
        parts.append(_t("{n} travail(s) en cours").format(n=active))
    return " · ".join(parts)
