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

_MARKER_MSG  = "══════════ MESSAGE ══════════"
_MARKER_PLAN = "══════════ PLAN ══════════"


def _plan_coedit_system(edition: str, mode: str = "live") -> str:
    if edition == "cinema":
        fmt = (
            "FORMAT DU PLAN RÉÉCRIT (respecte-le À L'IDENTIQUE) :\n"
            "P<NN> | Valeur de plan | Mouvement de caméra | Axe | ~Durée\n"
            "INT./EXT. LIEU PRÉCIS — MOMENT\n"
            "Description de l'action au présent, concrète et visuelle.\n"
            "→ SEEDANCE: prompt vidéo court, descriptif, sensoriel, en français.\n\n"
            "- Garde le MÊME numéro de plan (P<NN>) que l'original.\n"
            "- Valeurs de plan / mouvements / axes : reprends la nomenclature PANDORA.\n"
            "- Durée : notation ~Xs, maximum absolu ~15s."
        )
    else:
        _m = ("vidéo-mapping projeté sur une façade (géométrie du bâtiment conservée)"
              if mode == "mapping" else "set live / VJ")
        fmt = (
            f"CONTEXTE : conducteur d'un {_m}.\n"
            "FORMAT DU PLAN RÉÉCRIT (respecte-le À L'IDENTIQUE) :\n"
            "PLAN <n> — Titre court en français\n"
            "Durée : <x>s · Valeur de plan : … · Mouvement : …\n"
            "PROMPT VIDÉO (Seedance 2.0, anglais) : \"…\"\n"
            "PROMPT SON (sound design / SFX, anglais) : \"…\"\n\n"
            "- Garde le MÊME numéro de plan (PLAN <n>) que l'original.\n"
            "- Le PROMPT VIDÉO reste en ANGLAIS, très détaillé (beats début/milieu/fin).\n"
            "- Le PROMPT SON reste en ANGLAIS (SFX/ambiance uniquement, aucune voix).\n"
            "- Durée entière entre 4 et 15 secondes."
        )
    return (
        "Tu es directeur de la photographie et superviseur de production sur PANDORA "
        "(pré-production IA, génération vidéo via Seedance 2.0). Tu travailles avec le "
        "réalisateur EN CO-ÉCRITURE sur UN SEUL plan de sa mise en page, pour le "
        "réécrire et l'enrichir jusqu'à ce qu'il soit prêt pour la génération.\n\n"
        "On te fournit : la MISE EN PAGE COMPLÈTE (contexte, à ne PAS réécrire), le "
        "PLAN CIBLE à retravailler, et la demande du réalisateur. Des images de "
        "référence peuvent être jointes : ce sont des INSPIRATIONS (ambiances, "
        "matières, lumières, cadrages) à transposer, JAMAIS à copier ni à décrire "
        "littéralement.\n\n"
        "Tu ne modifies QUE le plan cible. Tu ne renvoies QUE ce plan. Tu restes "
        "cohérent avec le reste de la mise en page (continuité, personnages, décor).\n\n"
        + fmt +
        "\n\nRÉPONDS TOUJOURS EN DEUX BLOCS, dans cet ordre exact :\n"
        f"{_MARKER_MSG}\n"
        "(1 à 3 phrases au réalisateur : ce que tu as changé et pourquoi.)\n"
        f"{_MARKER_PLAN}\n"
        "(le plan réécrit, au format ci-dessus, et RIEN d'autre.)"
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

    def run(self):
        try:
            from core.ai_provider import chat as ai_chat, key_error
            err = key_error("screenplay")
            if err:
                self.failed.emit(err)
                return

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

            # Message courant — multimodal si images de référence
            if self._refs:
                import base64, os as _os
                _MT = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                       "webp": "image/webp", "gif": "image/gif"}
                cur: list = []
                for path in self._refs[:4]:
                    try:
                        with open(path, "rb") as fh:
                            data = base64.b64encode(fh.read()).decode()
                        ext = _os.path.splitext(path)[1].lower().lstrip(".")
                        cur.append({"type": "image",
                                    "source": {"type": "base64",
                                               "media_type": _MT.get(ext, "image/jpeg"),
                                               "data": data}})
                    except Exception:
                        pass
                prefix = context_block + "\n\n" if not messages else ""
                cur.append({"type": "text", "text": prefix + self._user})
                messages.append({"role": "user", "content": cur})
            else:
                if not messages:
                    messages.append({"role": "user",
                                     "content": context_block + "\n\n" + self._user})
                else:
                    messages.append({"role": "user", "content": self._user})

            system = _plan_coedit_system(self._edition, self._mode)

            if self._refs:
                # VISION (images jointes) : direct Anthropic — hors couche ai_provider.
                import anthropic
                from core.config import load_config as _lc
                client = anthropic.Anthropic(api_key=_lc().get("anthropic_key", "").strip())
                response = client.messages.create(
                    model=_VISION_MODEL, max_tokens=8192,
                    thinking=_VISION_NO_THINK, system=system, messages=messages)
                raw = response.content[0].text.strip()
            else:
                raw = ai_chat(system, messages, tier="creative",
                              max_tokens=8192, task="screenplay").strip()

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
