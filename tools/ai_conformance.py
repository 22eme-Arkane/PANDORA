"""tools/ai_conformance.py — Un moteur IA texte se comporte-t-il « comme Claude » ?

Batterie À LA DEMANDE contre un moteur réel (Ollama, serveur local LM Studio /
llama.cpp / vLLM / Jan, fournisseur personnalisé, Kimi, GLM, OpenAI, Mistral,
Anthropic) : les mêmes exigences que les workers de PANDORA — traduction nue,
tableau JSON, marqueurs exacts, objet JSON d'éditions, détection de la
troncature + continuation, pas de pensée dans la réponse, contexte long non
tronqué (le piège Ollama), vision si le modèle la revendique.

Ne touche JAMAIS à data/config.json : la configuration est SYNTHÉTIQUE
(core.ai_provider._cfg remplacé pour la durée du script).

    python tools/ai_conformance.py --provider ollama --model qwen3.5:latest
    python tools/ai_conformance.py --provider local --preset lmstudio --model qwen3-8b
    python tools/ai_conformance.py --provider ollama --model qwen2.5vl:7b --only vision,pensee
    python tools/ai_conformance.py --provider anthropic --model claude-sonnet-5 --key sk-ant-…

Sortie : un tableau OK/ÉCHEC par épreuve, code de retour = nombre d'échecs.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import time
import unicodedata

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import ai_provider as AP          # noqa: E402
from core.local_llm import LOCAL_PRESETS   # noqa: E402


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def _fenced(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def _json_between(text: str, opener: str, closer: str):
    t = _fenced(text)
    a, b = t.find(opener), t.rfind(closer)
    if a < 0 or b < 0:
        raise ValueError("pas de " + opener)
    return json.loads(t[a:b + 1])


# ── Épreuves ─────────────────────────────────────────────────────────────────

_SCENARIO = """INT. PHARE — NUIT
MARGUERITE (60 ans, gardienne du phare, ciré jaune) vérifie la lampe. Son neveu
THÉO (17 ans, capuche, casque audio autour du cou) monte l'escalier en trombe.
THÉO : Tante Margue, il y a un bateau sur les rochers !
MARGUERITE (sans se retourner) : Alors on descend.
EXT. ROCHERS — NUIT
Le CAPITAINE ARNAUD (45 ans, barbe rousse, uniforme trempé) se hisse sur la
pierre en tenant un coffre de bois."""


def t_traduction():
    out = AP.complete("Tu traduis du français vers l'anglais.",
                      "Traduis en anglais : « Le phare s'éteint quand la mer se calme. »",
                      tier="utility", max_tokens=120, task="translate")
    low = _norm(out)
    ok = ("lighthouse" in low and "voici" not in low and "here is" not in low
          and not out.strip().startswith("```") and len(out.strip().splitlines()) <= 2)
    return ok, out


def t_extraction_json():
    system = ("Extrais les PERSONNAGES du scénario. Réponds par un tableau JSON d'objets "
              "{\"name\": str, \"age\": str, \"description\": str} — rien d'autre.")
    out = AP.complete(system, _SCENARIO, tier="creative", max_tokens=1200, task="extraction")
    data = _json_between(out, "[", "]")
    names = [_norm(str(d.get("name", ""))) for d in data if isinstance(d, dict)]
    ok = len(names) >= 3 and any("marguerite" in n for n in names) and any("theo" in n for n in names)
    return ok, out


def t_marqueurs():
    system = ("Réponds en DEUX parties séparées par une ligne contenant EXACTEMENT "
              "══════════ ANALYSE ══════════ : d'abord le texte réécrit au passé simple, "
              "puis une analyse d'une phrase.")
    out = AP.complete(system, "Théo monte l'escalier. Marguerite vérifie la lampe.",
                      tier="creative", max_tokens=400, task="screenplay")
    # Même tolérance que les analyseurs de PANDORA (core/markers) : un « ═ »
    # perdu ne compte pas, le mot-clé et la position (après le texte) si.
    from core.markers import normalize_markers
    norm = normalize_markers(out, ("══════════ ANALYSE ══════════",))
    ok = "══════════ ANALYSE ══════════" in norm and norm.strip().index("══════════ ANALYSE") > 5
    return ok, out


def t_json_objet():
    system = ("Tu modifies un storyboard par conversation. Réponds UNIQUEMENT par un objet JSON "
              "{\"reply\": str, \"edits\": [{\"shot\": int, \"field\": str, \"value\": any}]}. "
              "Champs possibles : duration (secondes, entier), shot_size, camera_movement.")
    out = AP.chat(system, [{"role": "user", "content": "Passe le plan 3 à 6 secondes."}],
                  tier="creative", max_tokens=400, task="storyboard_chat")
    data = _json_between(out, "{", "}")
    edits = data.get("edits") or []
    ok = (isinstance(data.get("reply"), str) and edits and int(edits[0].get("shot", 0)) == 3
          and str(edits[0].get("field", "")).startswith("duration") and int(edits[0].get("value", 0)) == 6)
    return ok, out


def t_troncature():
    msgs = [{"role": "user", "content": "Raconte une histoire de 400 mots sur un gardien de phare."}]
    r1 = AP.chat_ex("Réponds en français.", msgs, tier="creative", max_tokens=40, task="screenplay")
    # 80 mots ≈ 150 jetons : la coupe à 120 force AU MOINS une continuation ; un
    # modèle qui respecte la longueur finit en 2-3 tours (budget total 840).
    r2 = AP.chat_until_complete_ex("Réponds en français, en 80 mots maximum, puis arrête-toi.",
                                   [{"role": "user", "content": "Raconte une histoire de 80 mots sur un gardien de phare."}],
                                   tier="creative", max_tokens=120, task="screenplay", max_rounds=6)
    ok = bool(r1.get("truncated")) and not r2.get("truncated") and len(r2.get("text", "")) > 200
    return ok, f"coupe détectée={r1.get('truncated')} · continuations={r2.get('rounds')} · " \
               f"fin propre={not r2.get('truncated')} · {len(r2.get('text', ''))} car."


def t_pensee():
    out = AP.complete("Réponds par un seul mot, sans ponctuation.", "Quelle est la capitale de la France ?",
                      tier="utility", max_tokens=60, task="assistant")
    low = _norm(out)
    ok = "<think" not in low and "paris" in low and len(out.strip()) < 40
    return ok, out


def t_contexte_long(chars: int):
    """L'aiguille est au DÉBUT : une fenêtre trop courte la perd (Ollama coupe le
    début du prompt en silence quand num_ctx n'est pas dimensionné)."""
    needle = "NOTE DE PRODUCTION : le mot de passe du plateau est ZEPHYR-42."
    body = []
    i = 1
    while sum(len(b) for b in body) < chars:
        body.append(f"\n\nSCÈNE {i} — INT. COULOIR — JOUR\nLe personnage {i} traverse le couloir, "
                    f"s'arrête devant la porte {i} et écoute. Un bruit de pas. Il repart.")
        i += 1
    text = needle + "".join(body)
    out = AP.complete("Tu réponds à une question sur un document. Réponds en une ligne.",
                      text + "\n\nQUESTION : quel est le mot de passe du plateau donné dans la note "
                             "de production, tout au début du document ?",
                      tier="utility", max_tokens=80, task="assistant")
    ok = "zephyr" in _norm(out) and "42" in out
    return ok, f"{len(text)} car. envoyés → {out.strip()[:120]}"


def t_vision():
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None, "Pillow absent"
    im = Image.new("RGB", (256, 256), "white")
    ImageDraw.Draw(im).ellipse((64, 64, 192, 192), fill=(220, 20, 20))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    out = AP.chat("Tu décris des images.",
                  [{"role": "user", "content": [
                      {"type": "text", "text": "Quelle forme géométrique et quelle couleur ? Réponds en cinq mots maximum."},
                      {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}}]}],
                  tier="utility", max_tokens=60, task="vision")
    low = _norm(out)
    ok = any(w in low for w in ("rouge", "red")) and any(w in low for w in ("cercle", "rond", "circle", "disque", "disc"))
    return ok, out


EPREUVES = [
    ("traduction",    "Traduction nue (sans préambule ni ```)",           lambda a: t_traduction()),
    ("extraction",    "Tableau JSON de personnages",                      lambda a: t_extraction_json()),
    ("marqueurs",     "Marqueurs ══════════ reproduits à l'identique",     lambda a: t_marqueurs()),
    ("json_objet",    "Objet JSON d'éditions (chat storyboard)",           lambda a: t_json_objet()),
    ("troncature",    "Coupe détectée + continuation jusqu'à la fin",      lambda a: t_troncature()),
    ("pensee",        "Aucun bloc <think> dans la réponse",                lambda a: t_pensee()),
    ("contexte_long", "Aiguille au début d'un long document",              lambda a: t_contexte_long(a.long_chars)),
    ("vision",        "Cercle rouge reconnu (image)",                      lambda a: t_vision()),
]


# ── Configuration synthétique ────────────────────────────────────────────────

def synthetic_cfg(a) -> dict:
    cfg = {"ai_profile": "single", "ai_provider": a.provider, "ai_engine": "",
           "ai_model_creative": a.model, "ai_task_engines": {}}
    if a.provider == "ollama":
        cfg.update({"ollama_model": a.model, "ollama_url": a.url or "", "ollama_num_ctx": a.num_ctx})
    elif a.provider == "local":
        cfg.update({"local_preset": a.preset, "local_url": a.url or "", "local_model": a.model,
                    "local_key": a.key or ""})
    elif a.provider in ("kimi", "glm", "custom"):
        cfg.update({f"{a.provider}_model": a.model, f"{a.provider}_url": a.url or "",
                    f"{a.provider}_key": a.key or ""})
    elif a.provider == "openai":
        cfg.update({"openai_model": a.model, "openai_key": a.key or ""})
    elif a.provider == "mistral":
        cfg.update({"mistral_key": a.key or ""})
    elif a.provider == "anthropic":
        cfg.update({"anthropic_key": a.key or ""})
    return cfg


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--provider", required=True, choices=AP._PROVIDERS)
    p.add_argument("--model", required=True)
    p.add_argument("--url", default="")
    p.add_argument("--key", default="")
    p.add_argument("--preset", default="lmstudio", choices=list(LOCAL_PRESETS))
    p.add_argument("--num-ctx", type=int, default=32768)
    p.add_argument("--long-chars", type=int, default=60000)
    p.add_argument("--only", default="", help="épreuves, séparées par des virgules")
    a = p.parse_args()

    cfg = synthetic_cfg(a)
    AP._cfg = lambda: cfg                       # jamais le vrai config.json
    AP.refresh_name_cache()
    only = {x.strip() for x in a.only.split(",") if x.strip()}
    print(f"Moteur : {a.provider} · {a.model}" + (f" · {a.url}" if a.url else "")
          + (f" · préréglage {a.preset}" if a.provider == "local" else ""))
    print(f"Nom affiché par PANDORA : {AP.ai_name()}\n")
    fails = 0
    for key, title, fn in EPREUVES:
        if only and key not in only:
            continue
        t0 = time.time()
        try:
            ok, detail = fn(a)
        except RuntimeError as e:
            # La garde vision de PANDORA a parlé : le modèle ne voit pas les
            # images — c'est le comportement attendu, pas un échec du moteur.
            if "ne voit pas les images" in str(e):
                ok, detail = None, "sans objet — " + str(e)[:160]
            else:
                ok, detail = False, f"{type(e).__name__}: {str(e)[:300]}"
        except Exception as e:
            ok, detail = False, f"{type(e).__name__}: {str(e)[:300]}"
        dt = time.time() - t0
        if ok is None:
            mark = "  —  "
        else:
            mark = "  OK " if ok else "ÉCHEC"
            fails += 0 if ok else 1
        one = " ".join(str(detail).split())[:160]
        print(f"[{mark}] {key:14s} {title:48s} {dt:6.1f} s   {one}")
    print(f"\n{fails} échec(s).")
    return fails


if __name__ == "__main__":
    sys.exit(main())
