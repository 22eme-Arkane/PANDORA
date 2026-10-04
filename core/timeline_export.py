"""
Export de timeline Final Cut Pro 7 XML (xmeml) — module NEUTRE (Cinéma et Live).

À importer dans DaVinci Resolve, gratuit ou Studio (Fichier → Importer →
Timeline), ou dans Adobe Premiere (Fichier → Importer). C'est la seule voie qui
reste ouverte à la version gratuite de Resolve depuis la 21.1, qui a retiré le
scripting Python.

Règles tirées de research_notes/Export timeline FCP7 XML/specification_xmeml.md
(04/10/2026), toutes sourcées :
  • structure calquée sur l'export natif de Premiere, séquence sous la racine
    (« Modeling your FCP XML on PPro's own is probably your best approach »,
    Bruce Bullis, Adobe) ; version 5, celle que Blackmagic déclare lire
    (« Resolve supports FCP 7 xml version 5 », Peter Chamberlain, 15/08/2023) ;
  • <format> TOUJOURS rempli : sans lui, Resolve fait de la timeline un clip
    noir (OpenTimelineIO #839, corrigé par la PR #1287 du 05/05/2022) ;
  • audio déclaré seulement si le fichier a VRAIMENT une piste audio : sinon
    « format mismatch » dans Premiere (otio-fcp-adapter #9, 05/08/2024) ;
  • stéréo = deux clipitems liés (A1 canal 1, A2 canal 2) avec les attributs de
    Premiere : Premiere recolle une piste stéréo, Resolve garde deux pistes mono
    complètes (fils Blackmagic 152017 et 159498) ;
  • out/end exclusifs, out ≤ nombre RÉEL d'images : Resolve refuse un clip dont
    l'étendue dépasse le fichier (« wrong timecode extents ») ;
  • timecode du fichier = son timecode réel (ffprobe), 00:00:00:00 à défaut ;
  • pathurl « file://localhost/C:/… », UTF-8 échappé en % (RFC 2396), jamais de
    « \\ » ;
  • ids de clipitem tirés du RANG, jamais d'un hachage du contenu (deux clips de
    même durée fusionnés : otio-fcp-adapter #10).
Aucune dépendance : xml.etree (Python 3.12 à 3.14).
"""

import json
import os
import re
import subprocess
import uuid
import xml.etree.ElementTree as ET
from collections import Counter
from urllib.parse import quote

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# ── Lecture des clips (ffprobe) ───────────────────────────────────────────────

def _fps_value(text: str) -> float:
    try:
        if "/" in text:
            num, den = text.split("/", 1)
            return float(num) / float(den) if float(den) else 0.0
        return float(text or 0)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def probe_clip(path: str) -> dict:
    """Ce que le XML doit dire du fichier : taille, cadence, nombre d'images,
    audio (canaux, fréquence), timecode, format de pixel."""
    info = {"path": path, "ok": False, "width": 0, "height": 0, "fps": 0.0, "frames": 0,
            "duration": 0.0, "has_audio": False, "channels": 0, "sample_rate": 48000,
            "timecode": "", "pix_fmt": ""}
    if not path or not os.path.isfile(path):
        return info
    try:
        from core.video_utils import get_ffprobe_exe
        run = subprocess.run(
            [get_ffprobe_exe(), "-v", "error", "-show_entries",
             "stream=codec_type,width,height,avg_frame_rate,r_frame_rate,nb_frames,"
             "pix_fmt,channels,sample_rate:stream_tags=timecode:format=duration:"
             "format_tags=timecode", "-of", "json", path],
            capture_output=True, text=True, timeout=30, creationflags=_NO_WINDOW)
        data = json.loads(run.stdout or "{}")
    except Exception:
        return info
    streams = data.get("streams") or []
    fmt = data.get("format") or {}
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    try:
        info["duration"] = float(fmt.get("duration") or 0.0)
    except (TypeError, ValueError):
        pass
    for source in [fmt] + streams:
        tc = ((source or {}).get("tags") or {}).get("timecode")
        if tc:
            info["timecode"] = str(tc)
            break
    if video:
        info["width"] = int(video.get("width") or 0)
        info["height"] = int(video.get("height") or 0)
        fps = _fps_value(video.get("avg_frame_rate") or "")
        if fps <= 0:
            fps = _fps_value(video.get("r_frame_rate") or "")
        info["fps"] = fps
        info["pix_fmt"] = str(video.get("pix_fmt") or "")
        try:
            info["frames"] = int(video.get("nb_frames") or 0)
        except (TypeError, ValueError):
            info["frames"] = 0
        if info["frames"] <= 0 and info["duration"] > 0 and fps > 0:
            # Arrondi vers le BAS : un « out » au-delà de la dernière image fait
            # refuser le clip par Resolve.
            info["frames"] = int(info["duration"] * fps + 1e-6)
    if audio:
        info["has_audio"] = True
        try:
            info["channels"] = int(audio.get("channels") or 2)
        except (TypeError, ValueError):
            info["channels"] = 2
        try:
            info["sample_rate"] = int(audio.get("sample_rate") or 48000)
        except (TypeError, ValueError):
            info["sample_rate"] = 48000
    info["ok"] = bool(video) and info["frames"] > 0 and info["fps"] > 0
    return info


# ── Briques du format ─────────────────────────────────────────────────────────

def rate_of(fps: float) -> tuple[int, bool]:
    """(timebase, ntsc) — table B-1 d'Apple : 23,976 → 24/TRUE, 29,97 → 30/TRUE…"""
    for nominal in (24, 30, 48, 60, 120):
        if abs(fps - nominal * 1000 / 1001) < 0.005:
            return nominal, True
    return (int(round(fps)) if fps > 0 else 24), False


def path_url(path: str) -> str:
    """URL de fichier lue par Premiere et par Resolve : file://localhost/C:/…
    (barres obliques, espaces et accents échappés en %)."""
    p = os.path.abspath(path).replace("\\", "/")
    if p.startswith("//"):                                  # partage réseau //serveur/…
        return "file:" + quote(p, safe="/:")
    if re.match(r"^[A-Za-z]:/", p):                         # lecteur Windows
        return "file://localhost/" + quote(p, safe="/:")
    return "file://localhost" + quote(p, safe="/")


def timecode_frames(text: str, timebase: int) -> int:
    """« HH:MM:SS:FF » (ou « ; ») → numéro d'image ; 0 si illisible."""
    parts = re.split(r"[:;.]", text or "")
    if len(parts) != 4:
        return 0
    try:
        h, m, s, f = (int(x) for x in parts)
    except ValueError:
        return 0
    return ((h * 60 + m) * 60 + s) * timebase + f


def timecode_string(frames: int, timebase: int) -> str:
    tb = max(1, timebase)
    f = frames % tb
    s = frames // tb
    return f"{s // 3600:02d}:{(s // 60) % 60:02d}:{s % 60:02d}:{f:02d}"


def _sub(parent, tag: str, text=None, **attrs):
    el = ET.SubElement(parent, tag, {k: str(v) for k, v in attrs.items()})
    if text is not None:
        el.text = str(text)
    return el


def _rate(parent, timebase: int, ntsc: bool):
    r = _sub(parent, "rate")
    _sub(r, "timebase", timebase)
    _sub(r, "ntsc", "TRUE" if ntsc else "FALSE")
    return r


def _timecode(parent, frames: int, timebase: int, ntsc: bool):
    tc = _sub(parent, "timecode")
    _rate(tc, timebase, ntsc)
    _sub(tc, "string", timecode_string(frames, timebase))
    _sub(tc, "frame", frames)
    _sub(tc, "displayformat", "NDF")
    return tc


def _video_chars(parent, width: int, height: int, timebase: int, ntsc: bool,
                 with_depth: bool = False):
    sc = _sub(parent, "samplecharacteristics")
    _rate(sc, timebase, ntsc)
    _sub(sc, "width", width)
    _sub(sc, "height", height)
    _sub(sc, "anamorphic", "FALSE")
    _sub(sc, "pixelaspectratio", "square")
    _sub(sc, "fielddominance", "none")
    if with_depth:
        _sub(sc, "colordepth", 24)
    return sc


def _link(parent, ref: str, mediatype: str, trackindex: int, clipindex: int,
          groupindex: int | None = None):
    lk = _sub(parent, "link")
    _sub(lk, "linkclipref", ref)
    _sub(lk, "mediatype", mediatype)
    _sub(lk, "trackindex", trackindex)
    _sub(lk, "clipindex", clipindex)
    if groupindex is not None:
        _sub(lk, "groupindex", groupindex)


# ── Construction de la séquence ───────────────────────────────────────────────

def build_xmeml(name: str, items: list[dict]) -> tuple[str, dict]:
    """Séquence de `items` posés bout à bout sur V1 (A1/A2 pour le son).

    Chaque item : {"path", "probe" (probe_clip), "title", "seq", "shot", "take",
    "action", "shot_id"}. Les items illisibles (probe["ok"] faux) sont écartés.
    → (texte XML, rapport : count, frames, timebase, ntsc, width, height,
       skipped, mixed_rate, ten_bit, non_ascii, silent)."""
    usable = [it for it in items if (it.get("probe") or {}).get("ok")]
    report = {"count": len(usable), "skipped": [it.get("path", "") for it in items
                                                 if not (it.get("probe") or {}).get("ok")],
              "mixed_rate": [], "ten_bit": [], "non_ascii": [], "silent": 0}
    if usable:
        seq_tb, seq_ntsc = Counter(rate_of(it["probe"]["fps"]) for it in usable).most_common(1)[0][0]
        width, height = Counter((it["probe"]["width"], it["probe"]["height"])
                                for it in usable).most_common(1)[0][0]
    else:
        seq_tb, seq_ntsc, width, height = 24, False, 1920, 1080
    seq_fps = seq_tb * (1000 / 1001 if seq_ntsc else 1)

    root = ET.Element("xmeml", {"version": "5"})
    seq = _sub(root, "sequence", id="sequence-1", explodedTracks="true")
    _sub(seq, "uuid", str(uuid.uuid4()))
    duration_el = _sub(seq, "duration", 0)
    _rate(seq, seq_tb, seq_ntsc)
    _sub(seq, "name", name)
    media = _sub(seq, "media")
    video = _sub(media, "video")
    fmt = _sub(video, "format")
    _video_chars(fmt, width, height, seq_tb, seq_ntsc, with_depth=True)
    v1 = _sub(video, "track")
    audio = _sub(media, "audio")
    _sub(audio, "numOutputChannels", 2)
    afmt = _sub(audio, "format")
    asc = _sub(afmt, "samplecharacteristics")
    _sub(asc, "depth", 16)
    _sub(asc, "samplerate", 48000)
    outputs = _sub(audio, "outputs")
    for ch in (1, 2):
        grp = _sub(outputs, "group")
        _sub(grp, "index", ch)
        _sub(grp, "numchannels", 1)
        _sub(grp, "downmix", 0)
        _sub(_sub(grp, "channel"), "index", ch)
    a_tracks = []
    for i in (0, 1):
        a_tracks.append(_sub(audio, "track", PannerIsInverted="true",
                             currentExplodedTrackIndex=i, totalExplodedTrackCount=2,
                             premiereTrackType="Stereo"))

    cursor = 0
    next_id = 1
    a_count = [0, 0]
    markers = []
    file_ids: dict[str, str] = {}       # un fichier décrit UNE fois, renvoyé ensuite
    for index, it in enumerate(usable, start=1):
        pr = it["probe"]
        tb, ntsc = rate_of(pr["fps"])
        src = int(pr["frames"])
        if (tb, ntsc) == (seq_tb, seq_ntsc):
            length = src
        else:
            length = max(1, int(round(src / pr["fps"] * seq_fps)))
            report["mixed_rate"].append(it["path"])
        if "10" in pr.get("pix_fmt", ""):
            report["ten_bit"].append(it["path"])
        try:
            it["path"].encode("ascii")
        except UnicodeEncodeError:
            report["non_ascii"].append(it["path"])
        start, end = cursor, cursor + length
        cursor = end
        title = it.get("title") or os.path.splitext(os.path.basename(it["path"]))[0]
        known_file = it["path"] in file_ids
        file_id = file_ids.setdefault(it["path"], f"file-{len(file_ids) + 1}")
        v_id = f"clipitem-{next_id}"
        next_id += 1
        channels = 0
        if pr.get("has_audio"):
            channels = 2 if int(pr.get("channels") or 2) >= 2 else 1
        else:
            report["silent"] += 1
        a_ids = [f"clipitem-{next_id + c}" for c in range(channels)]
        next_id += channels

        def _timing(el):
            _sub(el, "enabled", "TRUE")
            _sub(el, "duration", src)
            _rate(el, tb, ntsc)
            _sub(el, "start", start)
            _sub(el, "end", end)
            _sub(el, "in", 0)
            _sub(el, "out", src)

        def _links(el):
            if not a_ids:
                return
            _link(el, v_id, "video", 1, index)
            for c, a_id in enumerate(a_ids):
                _link(el, a_id, "audio", c + 1, a_count[c] + 1, 1)

        # ── Vidéo (V1) ──
        vc = _sub(v1, "clipitem", id=v_id)
        _sub(vc, "name", title)
        _timing(vc)
        _sub(vc, "alphatype", "none")
        _sub(vc, "pixelaspectratio", "square")
        _sub(vc, "anamorphic", "FALSE")
        fe = _sub(vc, "file", id=file_id)
        if not known_file:
            _sub(fe, "name", os.path.basename(it["path"]))
            _sub(fe, "pathurl", path_url(it["path"]))
            _rate(fe, tb, ntsc)
            _sub(fe, "duration", src)
            _timecode(fe, timecode_frames(pr.get("timecode", ""), tb), tb, ntsc)
            fmedia = _sub(fe, "media")
            _video_chars(_sub(fmedia, "video"), pr["width"], pr["height"], tb, ntsc)
            if channels:
                fa = _sub(fmedia, "audio")
                sc = _sub(fa, "samplecharacteristics")
                _sub(sc, "depth", 16)
                _sub(sc, "samplerate", int(pr.get("sample_rate") or 48000))
                _sub(fa, "channelcount", int(pr.get("channels") or channels))
        _links(vc)
        log = _sub(vc, "logginginfo")
        if it.get("action"):
            _sub(log, "description", it["action"])
        if it.get("seq"):
            _sub(log, "scene", it["seq"])
        if it.get("shot"):
            _sub(log, "shottake", f"{it['shot']}-{it.get('take') or 1}")
        if it.get("shot_id"):
            _sub(log, "lognote", f"PANDORA {it['shot_id']}")

        # ── Audio : A1 = canal 1, A2 = canal 2 (stéréo « éclatée » de Premiere) ──
        for c, a_id in enumerate(a_ids):
            ac = _sub(a_tracks[c], "clipitem", id=a_id,
                      premiereChannelType="stereo" if channels == 2 else "mono")
            _sub(ac, "name", title)
            _timing(ac)
            _sub(ac, "file", id=file_id)                    # renvoi au fichier déjà décrit
            st = _sub(ac, "sourcetrack")
            _sub(st, "mediatype", "audio")
            _sub(st, "trackindex", c + 1)
            _links(ac)
        for c in range(channels):
            a_count[c] += 1

        label = " · ".join(x for x in (
            f"SQ{it['seq']}" if it.get("seq") else "", f"P{it['shot']}" if it.get("shot") else "",
            f"prise {it['take']}" if it.get("take") else "") if x) or title
        markers.append((start, label, it.get("action") or ""))

    for c, track in enumerate(a_tracks):
        _sub(track, "enabled", "TRUE")
        _sub(track, "locked", "FALSE")
        _sub(track, "outputchannelindex", c + 1)
    _sub(v1, "enabled", "TRUE")
    _sub(v1, "locked", "FALSE")
    duration_el.text = str(cursor)
    _timecode(seq, 0, seq_tb, seq_ntsc)
    for start, label, comment in markers:
        mk = _sub(seq, "marker")
        _sub(mk, "comment", comment)
        _sub(mk, "name", label)
        _sub(mk, "in", start)
        _sub(mk, "out", -1)

    ET.indent(root, space="\t")
    text = ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n'
            + ET.tostring(root, encoding="unicode") + "\n")
    report.update({"frames": cursor, "timebase": seq_tb, "ntsc": seq_ntsc,
                   "width": width, "height": height})
    return text, report


def items_from_storyboard(clips: list[dict]) -> list[dict]:
    """Entrées de core.timeline_clips.storyboard_clips (avec clip) → items sondés."""
    items = []
    for c in clips:
        if not c.get("path"):
            continue
        shot = c.get("shot") or {}
        meta = c.get("meta") or {}
        items.append({
            "path": c["path"],
            "probe": probe_clip(c["path"]),
            "title": os.path.splitext(os.path.basename(c["path"]))[0],
            "seq": meta.get("Scene", ""),
            "shot": meta.get("Shot", ""),
            "take": meta.get("Take", ""),
            "action": str(shot.get("scene_title") or "").strip(),
            "shot_id": str(shot.get("id") or ""),
        })
    return items


def export_storyboard(path: str, name: str, clips: list[dict]) -> dict:
    """Sonde les clips, écrit le XML dans `path`. → rapport (+ "path", "ok")."""
    items = items_from_storyboard(clips)
    text, report = build_xmeml(name, items)
    if report["count"]:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    report["path"] = path
    report["ok"] = report["count"] > 0
    return report
