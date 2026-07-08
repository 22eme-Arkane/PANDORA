"""Co-écriture des plans — réécrire/enrichir UN plan de la « Mise en page PANDORA ».

Nouvel outil de finalisation (sélectionner un plan → dialoguer avec l'assistant →
réécrire/enrichir jusqu'à ce qu'il soit prêt pour la génération du découpage).

PARTAGÉ Cinéma ↔ Live (nouvelle fonctionnalité, pas un portage) : le paramètre
``edition`` calibre le format attendu du plan réécrit :
  - "cinema" : « P01 | Valeur | Mouvement | Axe | ~Durée » + « → SEEDANCE: »
  - "live"   : « PLAN n — Titre » + « PROMPT VIDÉO … » / « PROMPT SON … »

Le worker reçoit le plan cible + le contexte (mise en page complète) et ne renvoie
QUE ce plan réécrit — les autres plans restent intacts (édition chirurgicale).
Même pattern multimodal que ArrangeSessionChatConducteurWorker (marqueurs + vision).
"""
from PyQt6.QtCore import QThread, pyqtSignal

_VISION_MODEL    = "claude-sonnet-5"
_VISION_NO_THINK = {"type": "disabled"}

# Nombre max d'images de référence envoyées à l'assistant (source de vérité UNIQUE —
# le dialogue l'importe pour ne pas plafonner l'UI en-dessous). Large marge sous la
# limite API Anthropic (100 images/requête).
_MAX_REF_IMAGES = 12

_MARKER_MSG  = "══════════ MESSAGE ══════════"
_MARKER_PLAN = "══════════ PLAN ══════════"


def _fmt_block(edition: str, mode: str, _pl: str, _PL: str) -> str:
    """Bloc « FORMAT DU PLAN » (Cinéma « P0N | … » / Live « PLAN n — … »), partagé par
    la co-écriture d'un plan ET le correctif global par lots."""
    if edition == "cinema":
        return (
            "FORMAT DU PLAN RÉÉCRIT (respecte-le À L'IDENTIQUE) :\n"
            "P<NN> | Valeur de plan | Mouvement de caméra | Axe | ~Durée\n"
            "INT./EXT. LIEU PRÉCIS — MOMENT\n"
            "Description de l'action au présent, concrète et visuelle.\n"
            f"→ SEEDANCE: prompt vidéo court, descriptif, sensoriel, en {_pl}.\n\n"
            "- Pour le plan RETRAVAILLÉ, garde son numéro (P<NN>) ; pour un plan AJOUTÉ, "
            "mets un numéro placeholder au bon format (il sera réattribué automatiquement).\n"
            "- Valeurs de plan / mouvements / axes : reprends la nomenclature PANDORA.\n"
            "- Durée : notation ~Xs, maximum absolu ~15s."
        )
    _m = ("vidéo-mapping projeté sur une façade (géométrie du bâtiment conservée)"
          if mode == "mapping" else "set live / VJ")
    return (
        f"CONTEXTE : conducteur d'un {_m}.\n"
        "FORMAT DU PLAN RÉÉCRIT (respecte-le À L'IDENTIQUE) :\n"
        "PLAN <n> — Titre court en français\n"
        "Durée : <x>s · Valeur de plan : … · Mouvement : …\n"
        f"PROMPT VIDÉO ({_pl}) : \"…\"\n"
        f"PROMPT SON (sound design / SFX, {_pl}) : \"…\"\n\n"
        "- Pour le plan RETRAVAILLÉ, garde son numéro (PLAN <n>) ; pour un plan AJOUTÉ, "
        "mets un numéro placeholder au bon format (il sera réattribué automatiquement).\n"
        f"- Le PROMPT VIDÉO reste en {_PL}, très détaillé (beats début/milieu/fin).\n"
        f"- Le PROMPT SON reste en {_PL} (SFX/ambiance uniquement, aucune voix).\n"
        "- Durée entière entre 4 et 15 secondes."
    )


def _plan_coedit_batch_system(edition: str, mode: str = "live") -> str:
    """CORRECTIF GLOBAL par LOTS : applique une consigne à un SOUS-ENSEMBLE de plans et
    les renvoie TOUS corrigés (sans marqueur) — évite toute troncature sur une longue
    mise en page (la cause de la perte de plans)."""
    from core.i18n import get_lang
    _is_en = (get_lang() == "en")
    _pl = "anglais" if _is_en else "français"
    _PL = _pl.upper()
    return (
        "Tu es directeur de la photographie sur PANDORA. On te fournit un SOUS-ENSEMBLE de "
        "plans d'une mise en page et UNE consigne de correction à appliquer à CHACUN.\n\n"
        "Applique la correction à TOUS les plans fournis. Renvoie-les TOUS, corrigés, dans "
        "le MÊME ORDRE et le MÊME FORMAT, en conservant toute ligne d'en-tête d'acte "
        "« === ACTE … === » présente. Ne change QUE ce que la consigne implique ; garde le "
        "reste MOT POUR MOT. AUCUN marqueur, AUCUNE phrase autour — renvoie UNIQUEMENT les "
        "plans, chacun commençant par sa PROPRE ligne d'en-tête.\n\n"
        + _fmt_block(edition, mode, _pl, _PL)
    )


def _plan_coedit_system(edition: str, mode: str = "live", discuss_only: bool = False,
                        all_plans: bool = False) -> str:
    # Le plan réécrit reste dans la LANGUE DE TRAVAIL (fr/en) : la traduction en
    # anglais est faite au moment de l'ENVOI aux moteurs (translate_to_english) —
    # on garde donc le plan lisible et éditable dans la langue de l'utilisateur.
    # ``discuss_only`` : mode DISCUSSION (le plan n'est PAS réécrit — l'utilisateur
    # applique lui-même via « Modifier le plan »).
    # ``all_plans`` : CORRECTIF GLOBAL — la consigne s'applique à TOUS les plans et la
    # réponse (en modification) est la mise en page COMPLÈTE corrigée.
    from core.i18n import get_lang
    _is_en = (get_lang() == "en")
    _pl    = "anglais" if _is_en else "français"
    _PL    = _pl.upper()
    fmt = _fmt_block(edition, mode, _pl, _PL)
    _intro = (
        "Tu es directeur de la photographie et superviseur de production sur PANDORA "
        "(pré-production IA, génération vidéo via Seedance 2.0). Tu travailles avec le "
        "réalisateur EN CO-ÉCRITURE sur UN SEUL plan de sa mise en page, pour le "
        "réécrire et l'enrichir jusqu'à ce qu'il soit prêt pour la génération.\n\n"
        "On te fournit : la MISE EN PAGE COMPLÈTE (contexte, à ne PAS réécrire), le "
        "PLAN CIBLE à retravailler, et la demande du réalisateur. Des images de "
        "référence peuvent être jointes : ce sont des INSPIRATIONS (ambiances, "
        "matières, lumières, cadrages) à transposer, JAMAIS à copier ni à décrire "
        "littéralement.\n\n"
    )
    if discuss_only:
        # DISCUSSION : conseils/idées, AUCUNE réécriture, aucun bloc formaté.
        _scope = ("de la mise en page dans son ENSEMBLE (un correctif à appliquer à TOUS "
                  "les plans concernés)" if all_plans else "de ce plan")
        return (
            _intro +
            f"Tu DISCUTES avec le réalisateur À PROPOS {_scope} : conseils, idées, "
            "propositions de formulation, questions, retours critiques. Tu NE réécris "
            "PAS et tu ne renvoies AUCUN bloc de plan formaté ni marqueur — "
            f"réponds UNIQUEMENT en langage naturel, en {_pl}, de façon utile et "
            "concrète. C'est le réalisateur qui appliquera les changements lui-même via "
            "le bouton « Modifier ».\n\n"
            "Pour ta compréhension (NE le reproduis PAS dans ta réponse), voici le "
            "format d'un plan :\n" + fmt
        )
    if all_plans:
        # CORRECTIF GLOBAL : réécrit la mise en page COMPLÈTE avec la consigne appliquée
        # à tous les plans, en conservant la structure (actes, numéros, format).
        return (
            _intro +
            "CORRECTIF GLOBAL : le réalisateur te demande une correction à appliquer à "
            "TOUTE la mise en page. Applique-la à CHAQUE plan concerné, en conservant "
            "STRICTEMENT la structure (les éventuels en-têtes d'acte, l'ORDRE et le "
            "NOMBRE de plans, les numéros, et le FORMAT EXACT de chaque plan). Ne change "
            "QUE ce que la demande implique ; laisse le reste de chaque plan MOT POUR "
            "MOT.\n\n"
            "Format de chaque plan (à respecter à l'identique) :\n" + fmt +
            "\n\nRÉPONDS EN DEUX BLOCS, dans cet ordre exact :\n"
            f"{_MARKER_MSG}\n"
            "(1 à 3 phrases : ce que tu as corrigé et sur quels plans.)\n"
            f"{_MARKER_PLAN}\n"
            "(la mise en page COMPLÈTE corrigée — TOUS les actes et TOUS les plans du "
            "premier au dernier, au format ci-dessus, et RIEN d'autre.)"
        )
    return (
        _intro +
        "Tu retravailles le plan cible (SAUF si on te demande explicitement d'AJOUTER "
        "un nouveau plan — voir CAS PARTICULIER ci-dessous). Tu restes cohérent avec le "
        "reste de la mise en page (continuité, personnages, décor).\n\n"
        + fmt +
        "\n\nCAS PARTICULIER — CRÉER UN NOUVEAU PLAN : si le réalisateur te demande "
        "d'AJOUTER un plan (ex. « ajoute un plan entre le 26 et le 27 ») ou de SCINDER le "
        "plan cible en deux, tu PEUX renvoyer PLUSIEURS blocs de plan à la suite, dans "
        "l'ordre voulu (le plan retravaillé ET le/les nouveaux). Chaque bloc DOIT "
        "commencer par sa PROPRE ligne d'en-tête au format ci-dessus. INTERDIT : les "
        "mentions « bis », « ter » ou « 26b » ; fusionner deux plans dans un seul bloc ; "
        "décrire un second plan à l'intérieur du premier. Les numéros des nouveaux plans "
        "n'ont AUCUNE importance (ils seront réattribués automatiquement) — mets juste un "
        "numéro plausible au bon format. Si on ne te demande PAS d'ajouter de plan, "
        "renvoie UN SEUL bloc.\n\n"
        "RÉPONDS TOUJOURS EN DEUX BLOCS, dans cet ordre exact :\n"
        f"{_MARKER_MSG}\n"
        "(1 à 3 phrases au réalisateur : ce que tu as changé et pourquoi.)\n"
        f"{_MARKER_PLAN}\n"
        "(le plan réécrit — OU les plusieurs plans si on t'a demandé d'en ajouter — "
        "au format ci-dessus, et RIEN d'autre.)"
    )


class PlanCoEditWorker(QThread):
    """Réécrit UN plan de la mise en page via chat (multimodal si images jointes).

    Signaux :
        message_ready(str) — réponse conversationnelle (à afficher dans le chat)
        plan_ready(str)    — le plan réécrit (à réinjecter dans la mise en page)
        failed(str)        — message d'erreur humanisé
    """
    message_ready = pyqtSignal(str)
    plan_ready    = pyqtSignal(str)
    failed        = pyqtSignal(str)
    progress      = pyqtSignal(str)   # avancement du correctif global par lots

    def __init__(
        self,
        layout_text: str,
        plan_text: str,
        plan_label: str,
        history: list,
        user_message: str,
        edition: str = "cinema",
        mode: str = "live",
        ref_images: list | None = None,
        facade_path: str = "",
        discuss_only: bool = False,
        all_plans: bool = False,
    ):
        super().__init__()
        self._layout  = layout_text or ""
        self._plan    = plan_text or ""
        self._label   = plan_label or ""
        self._history = list(history or [])   # [{"role": "user"/"assistant", "content": str}]
        self._user    = user_message or ""
        self._edition = "cinema" if edition == "cinema" else "live"
        self._mode    = mode if mode in ("live", "mapping") else "live"
        self._refs    = list(ref_images or [])
        self._facade  = facade_path or ""     # façade réelle (mapping) : image à RESPECTER
        self._discuss = bool(discuss_only)    # DISCUSSION seule (ne réécrit pas le plan)
        self._all     = bool(all_plans)       # CORRECTIF GLOBAL sur TOUS les plans

    def run(self):
        try:
            from core.ai_provider import chat as ai_chat, key_error
            err = key_error("screenplay")
            if err:
                self.failed.emit(err)
                return

            # CORRECTIF GLOBAL (modif) : traité par LOTS pour ne JAMAIS tronquer (donc
            # ne jamais perdre de plans sur une longue mise en page).
            if self._all and not self._discuss:
                self._run_all_batched(ai_chat)
                return

            if self._all:
                # CORRECTIF GLOBAL : pas de plan cible — toute la mise en page.
                context_block = (
                    "MISE EN PAGE COMPLÈTE À CORRIGER DANS SON ENSEMBLE (applique la "
                    "demande à TOUS les plans concernés) :\n" + self._layout
                )
            else:
                context_block = (
                    "MISE EN PAGE COMPLÈTE (contexte — NE PAS réécrire) :\n"
                    f"{self._layout}\n\n"
                    f"PLAN CIBLE à retravailler ({self._label}) :\n{self._plan}"
                )

            # Historique : contexte injecté dans le 1er message user
            messages: list = []
            for i, msg in enumerate(self._history):
                if i == 0 and msg.get("role") == "user":
                    messages.append({"role": "user",
                                     "content": context_block + "\n\n" + msg["content"]})
                else:
                    messages.append(msg)

            # Façade réelle (mapping) : jointe en 1ʳᵉ image, à RESPECTER (pas une
            # inspiration). Les refs utilisateur suivent comme inspirations.
            import os as _os
            _facade_ok = (self._mode == "mapping" and self._facade
                          and _os.path.isfile(self._facade))
            _imgs = ([self._facade] if _facade_ok else []) \
                + [p for p in self._refs if p != self._facade]
            _imgs = _imgs[:_MAX_REF_IMAGES]

            # Message courant — multimodal si images (façade réelle + inspirations)
            if _imgs:
                from core.image_payload import encode_image_for_vision
                cur: list = []
                for path in _imgs:
                    # Redimensionne/compresse : une photo de façade pleine résolution
                    # dépasse la limite 10 Mo de Claude (erreur 400). ≤1568 px JPEG →
                    # toujours largement sous la limite.
                    if not (path and _os.path.isfile(path)):
                        continue
                    try:
                        mime, data = encode_image_for_vision(path)
                    except Exception:
                        continue
                    cur.append({"type": "image",
                                "source": {"type": "base64",
                                           "media_type": mime, "data": data}})
                _note = ""
                if _facade_ok:
                    _note = ("[IMAGE 1 = FAÇADE RÉELLE du bâtiment, à RESPECTER strictement "
                             "(fenêtres, portes, étages réels — n'invente pas d'ouvertures). "
                             "Les images suivantes sont des inspirations à transposer.]\n\n")
                prefix = (context_block + "\n\n" if not messages else "") + _note
                cur.append({"type": "text", "text": prefix + self._user})
                messages.append({"role": "user", "content": cur})
            else:
                if not messages:
                    messages.append({"role": "user",
                                     "content": context_block + "\n\n" + self._user})
                else:
                    messages.append({"role": "user", "content": self._user})

            system = _plan_coedit_system(self._edition, self._mode,
                                         discuss_only=self._discuss, all_plans=self._all)
            if _facade_ok:
                system = system + (
                    "\n\nCONTRAINTE FAÇADE (mapping) : l'IMAGE 1 jointe est la FAÇADE RÉELLE "
                    "du bâtiment. Respecte STRICTEMENT sa géométrie (fenêtres, portes, "
                    "étages, silhouette) — N'INVENTE PAS d'ouvertures ni d'éléments absents.")

            # Correctif global (modif) : la sortie = toute la mise en page → plafond haut
            # (comme la génération de la mise en page) pour ne pas tronquer.
            _max_out = 16000 if (self._all and not self._discuss) else 8192

            if _imgs:
                # VISION (images jointes) : direct Anthropic — hors couche ai_provider.
                import anthropic
                from core.config import load_config as _lc
                client = anthropic.Anthropic(api_key=_lc().get("anthropic_key", "").strip())
                response = client.messages.create(
                    model=_VISION_MODEL, max_tokens=_max_out,
                    thinking=_VISION_NO_THINK, system=system, messages=messages)
                raw = response.content[0].text.strip()
            else:
                raw = ai_chat(system, messages, tier="creative",
                              max_tokens=_max_out, task="screenplay").strip()

            if self._discuss:
                # DISCUSSION seule : toute la réponse est conversationnelle, aucun plan
                # n'est réécrit ni appliqué (l'utilisateur applique via « Modifier le plan »).
                self.message_ready.emit(raw.strip())
                return

            chat_msg = ""
            plan = ""
            if _MARKER_PLAN in raw:
                parts = raw.split(_MARKER_PLAN, 1)
                plan  = parts[1].strip()
                first = parts[0]
                chat_msg = (first.split(_MARKER_MSG, 1)[1].strip()
                            if _MARKER_MSG in first else first.strip())
            elif _MARKER_MSG in raw:
                chat_msg = raw.split(_MARKER_MSG, 1)[1].strip()
            else:
                chat_msg = raw

            if chat_msg:
                self.message_ready.emit(chat_msg)
            if plan:
                self.plan_ready.emit(plan)

        except Exception as e:
            from core.worker import humanize_api_error
            self.failed.emit(humanize_api_error(str(e)))

    # ── CORRECTIF GLOBAL par LOTS (anti-troncature / anti-perte) ──────────────
    def _run_all_batched(self, ai_chat):
        """Applique la consigne à TOUS les plans par petits LOTS (≤ _BATCH), puis
        réassemble et renumérote. Chaque lot est court → aucune troncature. GARDE-FOU
        ANTI-PERTE : si un lot renvoie moins de plans que demandé, on conserve les
        ORIGINAUX pour les manquants ; et si le total final < total initial, on N'APPLIQUE
        RIEN (échec) plutôt que de perdre des plans. Émet progress() puis plan_ready()."""
        import core.plan_layout as pl
        _BATCH = 6
        plans = pl.split_plans(self._layout)
        total = len(plans)
        if total == 0:
            from core.i18n import translate
            self.failed.emit(translate("Aucun plan à corriger."))
            return
        head = self._layout[:plans[0]["start"]]
        # Façade (mapping) : décrite en TEXTE une seule fois et injectée dans le système
        # (pas d'image par lot → plus léger, pas de limite 10 Mo, pas de vision répétée).
        facade_block = ""
        if self._mode == "mapping" and self._facade:
            try:
                from core.live_building import describe_facade, facade_context_block
                from core.i18n import get_lang
                _d = describe_facade(self._facade)
                if _d:
                    facade_block = facade_context_block(_d, "en" if get_lang() == "en" else "fr")
            except Exception:
                facade_block = ""
        system = _plan_coedit_batch_system(self._edition, self._mode) + facade_block

        out_blocks: list = []
        try:
            for i in range(0, total, _BATCH):
                batch = plans[i:i + _BATCH]
                n = len(batch)
                batch_text = "\n\n".join(b["text"] for b in batch)
                user = ("CONSIGNE à appliquer à CHAQUE plan ci-dessous :\n"
                        f"{self._user}\n\n"
                        "PLANS À CORRIGER (renvoie-les TOUS, corrigés, même ordre et "
                        f"format, et RIEN d'autre) :\n{batch_text}")
                raw = ai_chat(system, [{"role": "user", "content": user}],
                              tier="creative", max_tokens=8000, task="screenplay").strip()
                got = pl.split_plans(raw)
                if len(got) >= n:
                    out_blocks.extend(g["text"] for g in got[:n])
                else:
                    # Lot incomplet → on garde les ORIGINAUX pour les plans manquants.
                    out_blocks.extend(g["text"] for g in got)
                    out_blocks.extend(b["text"] for b in batch[len(got):])
                self.progress.emit(f"{min(i + n, total)}/{total}")
        except Exception as e:
            from core.worker import humanize_api_error
            self.failed.emit(humanize_api_error(str(e)))
            return

        combined = "\n\n".join(out_blocks)
        if head.strip():
            combined = head.rstrip() + "\n\n" + combined
        full = pl.renumber_all(combined)
        # GARDE-FOU ULTIME : jamais moins de plans qu'au départ → sinon on n'applique rien.
        if pl.plan_count(full) < total:
            from core.i18n import translate
            self.failed.emit(translate(
                "Correctif interrompu (réponse incomplète) — RIEN n'a été appliqué pour "
                "ne perdre aucun plan. Réessaie."))
            return
        self.plan_ready.emit(full)
