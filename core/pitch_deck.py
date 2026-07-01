"""
core/pitch_deck.py — Export d'un DOSSIER DE PRÉSENTATION (pitch deck) depuis le
storyboard PANDORA.

Génère un fichier HTML autonome (images encodées en base64 → aucun fichier
externe, aucune dépendance nouvelle) au thème cinéma PANDORA, structuré comme un
deck de présentation pour commanditaires / investisseurs :

    Couverture · Casting · Décors · Découpage plan par plan

Le fichier s'ouvre dans n'importe quel navigateur et s'imprime proprement en PDF
(Ctrl+P → « Enregistrer au format PDF ») — chaque section démarre sur une page.

Module PUR : ne dépend PAS de PyQt (testable headless). Les images sont
redimensionnées via Pillow (déjà une dépendance) pour garder le fichier léger ;
si Pillow échoue sur une image, celle-ci est simplement omise.
"""

import base64
import html as _html
import io
import os


# ── Encodage / vignettes ──────────────────────────────────────────────────────

def _img_data_uri(path: str, max_px: int = 520, quality: int = 82) -> str:
    """Charge une image locale, la redimensionne (côté max = max_px) et renvoie
    une data-URI JPEG base64. Retourne '' si le fichier est absent/illisible."""
    if not path or not os.path.isfile(path):
        return ""
    try:
        from PIL import Image
        with Image.open(path) as im:
            im = im.convert("RGB")
            w, h = im.size
            scale = min(1.0, float(max_px) / float(max(w, h) or 1))
            if scale < 1.0:
                im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))))
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=quality)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    except Exception:
        return ""


def _esc(text) -> str:
    return _html.escape(str(text or "").strip())


def _fmt_duration(total_s: float) -> str:
    total = int(round(total_s))
    m, s = divmod(total, 60)
    return f"{m} min {s:02d} s" if m else f"{s} s"


# ── i18n minimal (le module reste pur — pas d'import UI) ──────────────────────

_L = {
    "fr": {
        "deck":      "Dossier de présentation",
        "casting":   "Casting",
        "decors":    "Décors",
        "breakdown": "Découpage",
        "shots":     "plans",
        "total":     "durée totale",
        "seq":       "Séquence",
        "no_title":  "Sans titre",
        "made":      "Généré avec PANDORA",
    },
    "en": {
        "deck":      "Pitch deck",
        "casting":   "Cast",
        "decors":    "Locations",
        "breakdown": "Shot breakdown",
        "shots":     "shots",
        "total":     "total runtime",
        "seq":       "Sequence",
        "no_title":  "Untitled",
        "made":      "Made with PANDORA",
    },
}


# ── Construction HTML ─────────────────────────────────────────────────────────

_CSS = """
* { box-sizing: border-box; }
body { margin: 0; background: #0c0e1a; color: #e8e9f2;
       font-family: 'Segoe UI', system-ui, -apple-system, Arial, sans-serif; }
.slide { min-height: 100vh; padding: 56px 64px; page-break-after: always;
         border-bottom: 1px solid rgba(124,107,255,0.15); }
.slide:last-child { page-break-after: auto; }
.cover { display: flex; flex-direction: column; justify-content: center; align-items: center;
         text-align: center; background:
         radial-gradient(1200px 600px at 50% 20%, rgba(124,107,255,0.20), transparent 70%), #0c0e1a; }
.brand { letter-spacing: 8px; font-size: 14px; color: #7c6bff; font-weight: 700; margin-bottom: 24px; }
.cover h1 { font-size: 52px; font-weight: 800; margin: 0 0 12px; line-height: 1.1; max-width: 900px; }
.cover .sub { font-size: 17px; color: #a9abc4; margin-bottom: 40px; }
.cover .meta { font-size: 13px; color: #6f7290; font-family: 'Consolas', monospace; }
.sec-title { display: flex; align-items: baseline; gap: 14px; margin: 0 0 28px; }
.sec-title h2 { font-size: 30px; font-weight: 800; margin: 0; }
.sec-title .count { font-size: 13px; color: #7c6bff; font-family: 'Consolas', monospace; }
.grid { display: grid; gap: 20px; }
.grid.people { grid-template-columns: repeat(4, 1fr); }
.grid.locs   { grid-template-columns: repeat(3, 1fr); }
.grid.shots  { grid-template-columns: repeat(2, 1fr); }
.card { background: #14162b; border: 1px solid rgba(124,107,255,0.16);
        border-radius: 12px; overflow: hidden; }
.card img { width: 100%; display: block; object-fit: cover; background: #0a0b16; }
.people .card img { aspect-ratio: 3/4; }
.locs   .card img { aspect-ratio: 16/9; }
.shots  .card img { aspect-ratio: 16/9; }
.card .noimg { width: 100%; aspect-ratio: 16/9; display: flex; align-items: center;
        justify-content: center; color: #444a6b; font-size: 12px; background: #0a0b16; }
.card .body { padding: 12px 14px; }
.card .name { font-size: 14px; font-weight: 700; margin: 0 0 3px; }
.card .role { font-size: 11px; color: #8a8dab; }
.shot-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.badge { background: #7c6bff; color: #07080f; border-radius: 4px; font-size: 10px;
         font-weight: 800; padding: 2px 8px; font-family: 'Consolas', monospace; }
.shot-title { font-size: 14px; font-weight: 700; }
.shot-meta { font-size: 11px; color: #8a8dab; line-height: 1.6; }
.shot-meta b { color: #a9abc4; font-weight: 600; }
.seq-label { font-size: 12px; letter-spacing: 2px; color: #7c6bff; font-weight: 700;
             margin: 26px 0 12px; text-transform: uppercase; }
.foot { text-align: center; color: #4a4f70; font-size: 11px; margin-top: 40px; }
@media print {
  html, body { background: #0c0e1a !important;
               -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .slide { min-height: auto; }
}
"""


def build_pitch_deck_html(project: dict, shots: list, characters: list,
                          decors: list, lang: str = "fr",
                          date_str: str = "") -> str:
    """Assemble le HTML complet du deck. Fonction PURE (données → chaîne)."""
    t = _L.get(lang, _L["fr"])
    project = project or {}
    shots = shots or []
    characters = characters or []
    decors = decors or []

    title = _esc(project.get("name") or project.get("title") or t["no_title"])
    total_dur = sum(float(s.get("duration", 0) or 0) for s in shots)

    parts: list[str] = []
    parts.append(
        f"<!DOCTYPE html><html lang='{lang}'><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{title} — {_esc(t['deck'])}</title><style>{_CSS}</style></head><body>"
    )

    # ── Couverture ────────────────────────────────────────────────────────────
    meta_bits = [f"{len(shots)} {t['shots']}", f"{t['total']} {_fmt_duration(total_dur)}"]
    if date_str:
        meta_bits.append(_esc(date_str))
    parts.append(
        "<section class='slide cover'>"
        "<div class='brand'>P A N D O R A</div>"
        f"<h1>{title}</h1>"
        f"<div class='sub'>{_esc(t['deck'])}</div>"
        f"<div class='meta'>{'  ·  '.join(meta_bits)}</div>"
        "</section>"
    )

    # ── Casting ─────────────────────────────────────────────────────────────────
    if characters:
        cards = []
        for c in characters:
            uri = _img_data_uri(c.get("image_path", ""), max_px=440)
            img = (f"<img src='{uri}'>" if uri
                   else "<div class='noimg'>—</div>")
            role = _esc(c.get("role", ""))
            role_html = f"<div class='role'>{role}</div>" if role else ""
            cards.append(
                f"<div class='card'>{img}<div class='body'>"
                f"<div class='name'>{_esc(c.get('name', ''))}</div>{role_html}</div></div>"
            )
        parts.append(
            "<section class='slide'>"
            f"<div class='sec-title'><h2>{_esc(t['casting'])}</h2>"
            f"<span class='count'>{len(characters)}</span></div>"
            f"<div class='grid people'>{''.join(cards)}</div></section>"
        )

    # ── Décors ──────────────────────────────────────────────────────────────────
    if decors:
        cards = []
        for d in decors:
            uri = _img_data_uri(d.get("image_path", ""), max_px=560)
            img = (f"<img src='{uri}'>" if uri
                   else "<div class='noimg'>—</div>")
            cards.append(
                f"<div class='card'>{img}<div class='body'>"
                f"<div class='name'>{_esc(d.get('name', ''))}</div></div></div>"
            )
        parts.append(
            "<section class='slide'>"
            f"<div class='sec-title'><h2>{_esc(t['decors'])}</h2>"
            f"<span class='count'>{len(decors)}</span></div>"
            f"<div class='grid locs'>{''.join(cards)}</div></section>"
        )

    # ── Découpage plan par plan (groupé par séquence) ───────────────────────────
    if shots:
        body: list[str] = [
            "<section class='slide'>"
            f"<div class='sec-title'><h2>{_esc(t['breakdown'])}</h2>"
            f"<span class='count'>{len(shots)} {_esc(t['shots'])}</span></div>"
        ]
        cur_seq = object()   # sentinelle pour détecter le changement de séquence
        open_grid = False
        for s in shots:
            seq = s.get("seq_name", "") or ""
            if seq != cur_seq:
                cur_seq = seq
                if open_grid:
                    body.append("</div>")
                if seq:
                    body.append(f"<div class='seq-label'>{_esc(t['seq'])} — {_esc(seq)}</div>")
                body.append("<div class='grid shots'>")
                open_grid = True
            uri = _img_data_uri(s.get("image_path", ""), max_px=560)
            img = (f"<img src='{uri}'>" if uri
                   else "<div class='noimg'>—</div>")
            chars = ", ".join(s.get("character_names", []) or [])
            decor = _esc(s.get("decor_name", ""))
            dur = float(s.get("duration", 0) or 0)
            meta_lines = []
            if decor:
                meta_lines.append(f"<b>{_esc(t['decors'])[:-1] if lang=='fr' else 'Location'}:</b> {decor}")
            if chars:
                meta_lines.append(f"<b>{_esc(t['casting'])}:</b> {_esc(chars)}")
            meta_lines.append(f"<b>⏱</b> {dur:.0f}s")
            body.append(
                f"<div class='card'>{img}<div class='body'>"
                f"<div class='shot-head'><span class='badge'>P{_esc(s.get('number', '?'))}</span>"
                f"<span class='shot-title'>{_esc(s.get('scene_title', ''))}</span></div>"
                f"<div class='shot-meta'>{'<br>'.join(meta_lines)}</div>"
                f"</div></div>"
            )
        if open_grid:
            body.append("</div>")
        body.append(f"<div class='foot'>{_esc(t['made'])}</div></section>")
        parts.append("".join(body))

    parts.append("</body></html>")
    return "".join(parts)


def export_pitch_deck(out_path: str, project: dict | None = None,
                      shots: list | None = None, characters: list | None = None,
                      decors: list | None = None, lang: str | None = None,
                      date_str: str = "") -> str:
    """Rassemble les données du projet courant (si non fournies), construit le
    deck et l'écrit dans out_path (.html). Retourne le chemin écrit.

    Les paramètres explicites priment (utile pour les tests headless)."""
    if lang is None:
        try:
            from core.i18n import get_lang
            lang = get_lang()
        except Exception:
            lang = "fr"

    if project is None:
        try:
            import core.context as _ctx
            project = {"name": _ctx.get_project_name()} if hasattr(_ctx, "get_project_name") else {}
        except Exception:
            project = {}
    if shots is None:
        try:
            import core.storyboard as _sb
            shots = _sb.list_shots()
        except Exception:
            shots = []
    if characters is None:
        try:
            import core.casting as _ca
            characters = _ca.list_characters()
        except Exception:
            characters = []
    if decors is None:
        try:
            import core.decors as _dc
            decors = _dc.list_decors()
        except Exception:
            decors = []

    html_str = build_pitch_deck_html(project, shots, characters, decors,
                                     lang=lang or "fr", date_str=date_str)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_str)
    return out_path
