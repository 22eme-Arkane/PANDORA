"""
core/prompt_sync.py — Les DEUX prompts d'un plan, synchronisés dans les deux sens.

ARCHITECTURE (décision Matthieu, 2026-08-09)
--------------------------------------------
Le pipeline travaillait à l'envers : le Storyboard ne portait que le document
structuré (blocs français), et le prompt réellement envoyé était composé au
DERNIER moment par le Studio — invisible, volatil, jamais celui qu'on lisait.

Le sens juste :
  1. le découpage produit les DEUX prompts — structuré ET final — et les
     enregistre avec le plan ;
  2. modifier l'un recompose l'autre (deux sens, immédiat) ;
  3. le Studio LIT le final du plan ; il ne compose plus en régime nominal.

CE QUI GARANTIT LE WYSIWYG
--------------------------
Les deux directions passent par le MÊME composeur que le Studio
(`api.video_prompt.compose`) avec un contexte reconstruit DEPUIS LE PLAN
(durée, heure, style projet, fiches casting, bible visuelle, moteur visé,
forme d'essai). Le final stocké est donc celui que le Studio aurait composé.

CE QUE ÇA COÛTE — assumé
------------------------
Chaque composition est un appel IA texte. Au découpage : un appel PAR PLAN,
en parallèle (pool borné), dans la même passe que la génération — quand le
storyboard s'affiche, chaque plan a ses deux prompts. À l'édition : un appel
par plan modifié, débouncé (une rafale de frappes = un seul appel). Sans clé
IA : on n'appelle rien, le plan reste sans final et le Studio garde son filet
historique (composition à l'envoi).

⚠ Le worker de composition ne SAUVE jamais lui-même : il rend le texte, et le
scheduler (thread principal) l'applique au plan — en le JETANT si le plan a
encore changé entre-temps. On n'écrase jamais une édition plus récente.
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal


# ── Heure du plan → contrainte d'éclairage anglaise ──────────────────────────
# SOURCE UNIQUE : tab_t2v (Studio) pointe sur cette table. Elle vivait en
# doublon dans l'UI — la moindre retouche aurait divergé entre Studio et sync.
SHOT_TIME_EN = {
    "Jour":              "strict daylight, natural midday sun, bright neutral "
                         "light, no golden hour, no sunset",
    "Nuit":              "nighttime scene, dark environment, night lighting, "
                         "no daylight, moonlight or artificial light",
    "Lever du soleil":   "sunrise, warm golden morning light, sun just above "
                         "the horizon, soft pink-orange sky",
    "Coucher du soleil": "sunset, golden hour, warm amber-orange light, sun "
                         "low on the horizon",
}


# ── Contexte de composition — depuis le PLAN, jamais depuis l'UI ─────────────

def context_for_shot(shot: dict) -> dict:
    """Le contexte que le Studio construit depuis ses widgets, reconstruit ici
    depuis le plan seul. Mêmes clés que tab_t2v._compose_context — c'est ce qui
    rend le final stocké identique à celui que le Studio composait."""
    shot = shot or {}
    try:
        from api.video_prompt import (character_notes_for_shot as _cn,
                                      visual_context_for_shot as _vc)
        cnotes, vctx = _cn(shot), _vc(shot)
    except Exception:
        cnotes = vctx = ""
    try:
        import core.style as _sa
        style_suffix = _sa.get_video_suffix()
    except Exception:
        style_suffix = ""
    try:
        from core.prompt_sections import sound_of as _so
        sound_notes = _so(shot.get("seedance_prompt", "") or "")
    except Exception:
        sound_notes = ""
    try:
        from core.target_engine import get_target_engine
        engine = get_target_engine()
    except Exception:
        engine = ""
    return {
        "style_suffix":    style_suffix,
        "time_suffix":     SHOT_TIME_EN.get((shot.get("shot_time") or "").strip(), ""),
        "duration":        shot.get("duration") or None,
        "character_notes": cnotes,
        "visual_context":  vctx,
        "sound_notes":     sound_notes,
        "audio":           True,
        "dialogue_lang":   shot.get("dialogue_lang", "en") or "en",
        "engine":          engine,
    }


# Clé PRIVÉE posée sur la copie d'un plan quand sa composition a échoué : elle
# porte la RAISON. Sans elle, le lot ne pouvait qu'accuser la clé IA — ce qu'il
# a fait alors que la clé marchait (constat Matthieu 2026-08-11 : 8 plans
# composés, 4 refusés, message « vérifiez la clé IA »). Jamais enregistrée
# dans le projet : elle est retirée avant toute sauvegarde.
E_REASON = "_compose_error"


def failure_reasons(copies: list) -> list:
    """[(numéro ou id du plan, raison)] des plans NON composés."""
    out = []
    for c in copies or []:
        why = (c or {}).get(E_REASON, "")
        if why:
            label = str(c.get("number") or c.get("id") or "?")
            out.append((label, why))
    return out


# ── Briques d'injection — SOURCE UNIQUE (Studio + synchronisation) ───────────

def apply_injections(text: str, injections: list) -> str:
    """Applique des briques [(label, texte, mode)] à un prompt, dans l'ordre.

    Déplacée ICI depuis tab_t2v (qui la réutilise) : la synchronisation doit
    assembler EXACTEMENT comme le Studio, sinon le final stocké n'est pas
    celui que le Studio aurait envoyé."""
    fp = (text or "").strip()
    for _label, txt, mode in injections or []:
        txt = (txt or "").strip()
        if not txt:
            continue
        if mode == "ctx":
            fp = txt + fp
        elif mode == "dash_prefix":
            fp = f"{txt} — {fp}"
        elif mode == "nl_prefix":
            fp = f"{txt}\n{fp}"
        elif mode == "comma_prefix":
            fp = f"{txt.rstrip(' .')}, {fp}"
        else:   # comma_suffix — pas de « ., » disgracieux
            fp = f"{fp.rstrip(' .')}, {txt}"
    return fp


def plan_injections(shot: dict) -> list:
    """Briques pré-composition qui viennent DU PLAN (jamais des réglages du
    Studio) : les termes caméra — valeur, AXE, focale, profondeur, distance,
    hauteur, mouvement, vitesse — et le « no subtitles » par défaut du produit.

    C'est le trou trouvé par Matthieu le 2026-08-11 : le Studio injectait
    `camera_terms` avant de composer, la synchronisation composait le prompt
    NU — l'axe caméra n'atteignait jamais le final écrit au découpage."""
    inj = []
    try:
        from core.shot_terms import camera_terms
        bits = camera_terms(shot or {})
        if bits:
            inj.append(("Caméra du plan (valeur, axe, focale, distance, "
                        "hauteur, mouvement, vitesse)",
                        ", ".join(bits), "dash_prefix"))
    except Exception:
        pass
    inj.append(("Sous-titres désactivés", "no subtitles", "comma_suffix"))
    return inj


# ── Direction 1 : structuré → final ──────────────────────────────────────────

def compose_final_for_shot(shot: dict, save: bool = True) -> str:
    """Compose le prompt FINAL du plan depuis son prompt structuré, et le range
    dans le plan (champs core/final_prompt). Renvoie le texte, ou "" si la
    composition a échoué / est impossible (pas de clé, prompt vide).

    Appel RÉSEAU — à exécuter dans un thread, jamais sur le thread UI.
    """
    shot = shot or {}
    shot.pop(E_REASON, None)
    structured = (shot.get("seedance_prompt") or "").strip()
    if not structured:
        shot[E_REASON] = "plan sans prompt structuré"
        return ""
    try:
        from core.ai_provider import key_error
        _ke = key_error("video_prompt")
        if _ke:
            shot[E_REASON] = _ke      # pas de clé : le Studio composera à l'envoi
            return ""
    except Exception:
        pass
    try:
        from api.video_prompt import compose
        from core.prompt_sections import strip_for_video
        ctx = context_for_shot(shot)
        # MÊME corps que le Studio : sections sans le SON (capturé à part) +
        # briques du PLAN — dont les termes caméra (l'AXE en fait partie).
        body = apply_injections(strip_for_video(structured),
                                plan_injections(shot))
        final = compose(
            body,
            style_suffix=ctx["style_suffix"], time_suffix=ctx["time_suffix"],
            duration=ctx["duration"], character_notes=ctx["character_notes"],
            include_sound=bool(ctx["audio"]), sound_notes=ctx["sound_notes"],
            visual_context=ctx["visual_context"], engine=ctx["engine"],
        )
    except Exception as _e:
        shot[E_REASON] = str(_e)[:200]
        return ""
    if not final:
        # Pourquoi le composeur a rendu vide : erreur API (crédits, quota) OU
        # prose refusée par la validation (dialogue altéré, préambule…).
        try:
            from api.video_prompt import LAST_COMPOSE_ERROR as _lce
        except Exception:
            _lce = ""
        shot[E_REASON] = _lce or "le composeur n'a rien rendu"
        return ""
    try:
        from core import final_prompt as _fp, prompt_form as _pfm
        shot[_fp.F_TEXT]   = final
        shot[_fp.F_SRC]    = structured
        shot[_fp.F_ENGINE] = ctx["engine"]
        shot[_fp.F_FORM]   = _pfm.get_form()
        # Empreinte du CONTEXTE hors-prompt (axe, heure, durée, langue…) :
        # c'est elle qui rend un final « périmé » quand un champ du tableau
        # change SANS toucher au texte structuré.
        shot[_fp.F_CTX] = _fp.ctx_fingerprint(shot)
        if save:
            shot.pop(E_REASON, None)   # diagnostic : jamais dans le projet
            import core.storyboard as _sb
            _sb.save_shot(shot)
    except Exception:
        pass
    return final


def compose_finals_for_shots(shots: list, max_workers: int = 6,
                             progress_cb=None) -> int:
    """Compose le final de CHAQUE plan d'un découpage, en parallèle borné.

    Appelée par le worker de génération du storyboard, dans SA passe : quand
    les plans arrivent à l'écran, les deux prompts existent. Ne sauve pas (les
    plans ne sont pas encore enregistrés à ce stade — l'appelant s'en charge),
    ne lève jamais, s'arrête net si la clé IA manque. Renvoie le nombre de
    plans effectivement composés.
    """
    shots = [s for s in (shots or []) if isinstance(s, dict)]
    if not shots:
        return 0
    try:
        from core.ai_provider import key_error
        if key_error("video_prompt"):
            return 0
    except Exception:
        return 0
    import concurrent.futures as _fut
    done = 0
    total = len(shots)
    with _fut.ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as pool:
        futures = {pool.submit(compose_final_for_shot, s, False): s for s in shots}
        for f in _fut.as_completed(futures):
            try:
                if f.result():
                    done += 1
            except Exception:
                pass
            if progress_cb:
                try:
                    progress_cb(done, total)
                except Exception:
                    pass
    return done


# ── Direction 2 : final → structuré ──────────────────────────────────────────

_SYSTEM_REVERSE = """Tu es un assistant de storyboard cinéma. On te donne le prompt vidéo FINAL
d'un plan (prose anglaise envoyée au moteur) et tu le redécoupes en sections
françaises de travail. Réponds UNIQUEMENT un objet JSON avec ces clés :
{"action": "...", "staging": "...", "ambiance": "...", "decor": "...", "lighting": "..."}

- "action"   : ce qui se passe (gestes, déroulé), en français.
- "staging"  : personnages présents et leur placement dans le cadre.
- "ambiance" : atmosphère / ton du plan.
- "decor"    : le lieu, tel que la prose le décrit.
- "lighting" : l'intention de lumière (sans consigne technique).
- Les dialogues entre guillemets restent VERBATIM (même langue, mêmes mots).
- N'invente RIEN qui ne soit pas dans la prose. Une section sans matière = "".
- JSON seul, sans commentaire ni préambule."""


def structured_from_final(shot: dict, final_text: str) -> str:
    """Reconstruit le prompt STRUCTURÉ depuis un final édité à la main.

    L'IA ne rend que les sections descriptives ; la TECHNIQUE reste déterministe
    (champs caméra du plan), le SON et le STYLE sont repris de l'ancien
    structuré — la prose finale les intègre sans les délimiter, les faire
    deviner par l'IA les corromprait. Renvoie "" en cas d'échec (l'appelant ne
    touche alors à rien). Appel RÉSEAU — jamais sur le thread UI.
    """
    final_text = (final_text or "").strip()
    if not final_text:
        return ""
    try:
        from core.ai_provider import complete, key_error
        if key_error("video_prompt"):
            return ""
        raw = (complete(_SYSTEM_REVERSE, final_text, tier="creative",
                        max_tokens=4096, task="video_prompt") or "").strip()
    except Exception:
        return ""
    import json as _json
    start, end = raw.find("{"), raw.rfind("}") + 1
    if start == -1 or end <= 0:
        return ""
    try:
        parts = _json.loads(raw[start:end])
    except Exception:
        return ""
    if not isinstance(parts, dict):
        return ""
    try:
        from core.prompt_sections import (build, parse, technique_line,
                                          LIGHTING_NOTE)
        old = parse((shot or {}).get("seedance_prompt", "") or "")
        lighting = (parts.get("lighting") or "").strip()
        if lighting and LIGHTING_NOTE not in lighting:
            lighting = f"{lighting} {LIGHTING_NOTE}"
        return build(
            action=(parts.get("action") or "").strip(),
            staging=(parts.get("staging") or "").strip(),
            ambiance=(parts.get("ambiance") or "").strip(),
            decor=(parts.get("decor") or "").strip(),
            lighting=lighting,
            technique=technique_line(shot or {}),
            sound=old.get("sound", ""),
            style=old.get("style", ""),
        )
    except Exception:
        return ""


# ── Workers Qt (édition dans le Storyboard) ──────────────────────────────────

class _SyncWorker(QThread):
    """Une synchronisation d'UN plan, dans UNE direction. Ne sauve rien :
    le résultat remonte par `done` et le scheduler l'applique (ou le jette).

    `done` porte la SOURCE photographiée au départ : c'est elle qui permet au
    scheduler de jeter un résultat devenu obsolète (le plan a rebougé pendant
    la composition) sans fouiller dans la liste des workers."""
    done   = pyqtSignal(str, str, str, str)  # (shot_id, direction, produit, source)
    failed = pyqtSignal(str)

    def __init__(self, shot: dict, direction: str):
        super().__init__()
        self._shot      = dict(shot or {})          # photographie à la planification
        self._direction = direction                 # "final" | "structured"

    def run(self):
        try:
            sid = str(self._shot.get("id") or "")
            src = (self._shot.get("seedance_prompt") or "").strip()
            if self._direction == "final":
                out = compose_final_for_shot(self._shot, save=False)
            else:
                out = structured_from_final(
                    self._shot, self._shot.get("_edited_final", ""))
            self.done.emit(sid, self._direction, out or "", src)
        except Exception as e:
            try:
                self.failed.emit(str(e)[:200])
            except Exception:
                pass


class PromptSyncScheduler(QObject):
    """Débounce + application des synchronisations, côté thread principal.

    Une rafale d'éditions sur le même plan = UN appel IA, lancé 1,5 s après la
    dernière. Le résultat n'est appliqué que si le plan n'a pas rebougé depuis
    (comparaison avec la source photographiée) — jamais d'écrasement.
    """
    synced = pyqtSignal(str)             # shot_id dont les prompts ont bougé

    _DEBOUNCE_MS = 1500

    def __init__(self):
        super().__init__()
        self._pending: dict[str, dict] = {}     # shot_id → {shot, direction, timer}
        self._workers: list = []                # anti-GC (règle maison)

    # — planification —

    def schedule_final(self, shot: dict):
        """Le structuré a changé → recomposer le final (débouncé)."""
        self._schedule(shot, "final")

    def schedule_structured(self, shot: dict, edited_final: str):
        """Le final a changé → reconstruire le structuré (débouncé)."""
        shot = dict(shot or {})
        shot["_edited_final"] = edited_final
        self._schedule(shot, "structured")

    def _schedule(self, shot: dict, direction: str):
        sid = str((shot or {}).get("id") or "")
        if not sid:
            return
        try:
            from core.ai_provider import key_error
            if key_error("video_prompt"):
                return              # pas de clé : le filet Studio reste le chemin
        except Exception:
            return
        prev = self._pending.get(sid)
        if prev and prev.get("timer"):
            prev["timer"].stop()
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda s=sid: self._fire(s))
        self._pending[sid] = {"shot": dict(shot), "direction": direction,
                              "timer": timer}
        timer.start(self._DEBOUNCE_MS)

    # — exécution —

    def _fire(self, sid: str):
        job = self._pending.pop(sid, None)
        if not job:
            return
        w = _SyncWorker(job["shot"], job["direction"])
        w.done.connect(self._on_done)
        # Parquer les terminés (jamais terminate(), règle maison anti-segfault).
        self._workers = [x for x in self._workers if x.isRunning()]
        self._workers.append(w)
        w.start()

    def _on_done(self, sid: str, direction: str, text: str, src: str):
        if not text:
            return
        try:
            import core.storyboard as _sb
            from core import final_prompt as _fp, prompt_form as _pfm
            shot = next((s for s in _sb.list_shots() if str(s.get("id")) == sid), None)
            if shot is None:
                return
            if direction == "final":
                # Le structuré a-t-il ENCORE changé pendant la composition ?
                # (src = photographie du worker au départ)
                if src and src != (shot.get("seedance_prompt") or "").strip():
                    return          # plus récent → on jette, un resync suivra
                shot[_fp.F_TEXT]   = text
                shot[_fp.F_SRC]    = (shot.get("seedance_prompt") or "").strip()
                try:
                    from core.target_engine import get_target_engine
                    shot[_fp.F_ENGINE] = get_target_engine()
                except Exception:
                    pass
                shot[_fp.F_FORM] = _pfm.get_form()
                shot[_fp.F_CTX]  = _fp.ctx_fingerprint(shot)
            else:
                # final → structuré : le nouveau structuré devient la source,
                # et le contexte courant devient l'empreinte de référence.
                shot["seedance_prompt"] = text
                shot[_fp.F_SRC] = text
                shot[_fp.F_CTX] = _fp.ctx_fingerprint(shot)
            _sb.save_shot(shot)
            self.synced.emit(sid)
        except Exception:
            pass


class BatchComposeWorker(QThread):
    """Compose les prompts finals d'un LOT de plans (storyboard existant).

    Chaînon manquant pour les storyboards antérieurs à l'architecture « à
    l'endroit » : leurs plans n'ont pas de final stocké, et la vue « Prompt
    final » n'affichait qu'un avertissement SANS moyen d'agir (constat
    Matthieu 2026-08-11, projet ADAM ET EVE). Déclenché par un clic explicite
    — jamais par un simple affichage.

    Travaille sur des COPIES : l'application au storyboard passe ensuite par
    `apply_batch_results` (thread principal), qui JETTE tout résultat dont la
    source a bougé pendant la composition — même garde que l'édition."""
    progress = pyqtSignal(int, int)      # (composés, total)
    done     = pyqtSignal(list)          # copies composées (règle maison : done)
    failed   = pyqtSignal(str)

    def __init__(self, shots: list):
        super().__init__()
        self._copies = [dict(s) for s in (shots or []) if isinstance(s, dict)]

    def start(self, *a, **k):
        # ⚠ Anti-GC : la page qui a lancé le lot peut être DÉTRUITE avant sa
        # fin (changement de projet — cas réel du 2026-08-11). Si elle portait
        # la seule référence, le QThread serait ramassé EN COURS d'exécution →
        # « QThread: Destroyed while thread is still running » → abort de
        # l'app. Parqué ici jusqu'à sa fin (signal natif QThread.finished).
        _BATCH_KEEPALIVE.append(self)
        self.finished.connect(self._unpark)
        super().start(*a, **k)

    def _unpark(self):
        try:
            _BATCH_KEEPALIVE.remove(self)
        except ValueError:
            pass

    def run(self):
        try:
            compose_finals_for_shots(
                self._copies,
                progress_cb=lambda i, n: self.progress.emit(i, n))
            self.done.emit(self._copies)
        except Exception as e:
            try:
                self.failed.emit(str(e)[:200])
            except Exception:
                pass


_BATCH_KEEPALIVE: list = []


def shots_needing_final(shots: list) -> list:
    """Plans SANS final à jour (jamais composé, ou périmé). Ce compte pilote le
    libellé du bouton — l'utilisateur voit ce qu'il va payer avant de cliquer."""
    from core import final_prompt as _fp
    return [s for s in (shots or [])
            if isinstance(s, dict) and (s.get("seedance_prompt") or "").strip()
            and _fp.state_of(s) != _fp.FRESH]


def apply_batch_results(copies: list) -> int:
    """Applique au storyboard les finals composés sur des copies, et SAUVE.

    À appeler sur le THREAD PRINCIPAL (slot du signal `done`). Un résultat
    dont le plan a été modifié pendant la composition est jeté — on n'écrase
    jamais une édition plus récente. Renvoie le nombre de plans mis à jour."""
    from core import final_prompt as _fp
    import core.storyboard as _sb
    applied = 0
    try:
        alive = {str(s.get("id")): s for s in _sb.list_shots()}
    except Exception:
        return 0
    # ⚠ Ne PAS retirer E_REASON ici : l'appelant lit les raisons APRÈS
    # l'application. Elle ne peut pas fuir dans le projet — seuls les champs
    # F_* sont recopiés sur le plan vivant.
    for c in copies or []:
        text = (c or {}).get(_fp.F_TEXT, "")
        if not text:
            continue
        shot = alive.get(str(c.get("id")))
        if shot is None:
            continue
        src = (c.get(_fp.F_SRC) or "").strip()
        if src != (shot.get("seedance_prompt") or "").strip():
            continue          # le plan a bougé pendant la composition → jeté
        shot[_fp.F_TEXT]   = text
        shot[_fp.F_SRC]    = src
        shot[_fp.F_ENGINE] = c.get(_fp.F_ENGINE, "")
        shot[_fp.F_FORM]   = c.get(_fp.F_FORM, "")
        shot[_fp.F_CTX]    = c.get(_fp.F_CTX, "") or _fp.ctx_fingerprint(shot)
        try:
            _sb.save_shot(shot)
            applied += 1
        except Exception:
            pass
    return applied


_SCHEDULER: PromptSyncScheduler | None = None


def scheduler() -> PromptSyncScheduler:
    """Singleton paresseux (exige une QApplication vivante)."""
    global _SCHEDULER
    if _SCHEDULER is None:
        _SCHEDULER = PromptSyncScheduler()
    return _SCHEDULER
