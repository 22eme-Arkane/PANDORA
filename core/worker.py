from PyQt6.QtCore import QThread, pyqtSignal

# ── Annulation SÛRE d'un QThread ──────────────────────────────────────────────
# QThread.terminate() est dangereux : il tue le thread n'importe où dans son code,
# laissant Qt/Python dans un état corrompu → segfault sur l'opération suivante.
# À la place : on coupe les signaux (résultats ignorés), on demande l'interruption,
# et on garde une référence pour que le thread finisse tranquillement sans être
# ramassé par le GC pendant qu'il tourne encore.
_ABANDONED_THREADS: list = []

def abandon_thread(w) -> None:
    """Abandonne un QThread en cours sans le terminer brutalement (anti-segfault)."""
    if w is None:
        return
    try:
        w.blockSignals(True)
    except Exception:
        pass
    try:
        w.requestInterruption()
    except Exception:
        pass
    try:
        w.quit()
    except Exception:
        pass
    _ABANDONED_THREADS.append(w)
    # Purge les threads déjà terminés (sûrs à libérer)
    _ABANDONED_THREADS[:] = [t for t in _ABANDONED_THREADS if _still_running(t)]

def is_running(t) -> bool:
    """isRunning() SÛR : renvoie False au lieu de lever quand l'objet C++ du QThread
    a déjà été détruit.

    Appeler t.isRunning() directement lève « RuntimeError: wrapped C/C++ object of
    type … has been deleted » — typiquement depuis un slot branché sur destroyed,
    qui par construction se déclenche APRÈS la destruction côté C++ (crash réel à la
    fermeture du Live, 2026-07-26). Tout code qui teste un worker susceptible d'avoir
    été détruit doit passer par ici."""
    try:
        return t.isRunning()
    except Exception:
        return False


# Ancien nom interne, conservé : utilisé par abandon_thread ci-dessus.
_still_running = is_running


# Mots-clés d'un VRAI refus de facturation. « out of », « limit exceeded »,
# « quota », « balance » ou le simple mot « credit » y figuraient : un rejet
# de validation fal (« duration out of range », « file size limit exceeded »)
# ou l'erreur de crédit du fournisseur IA TEXTE (Anthropic : « Your credit
# balance is too low ») s'affichaient tous en « Crédits fal.ai insuffisants »
# — constat Matthieu 25/09/2026, alors que fal avait 13 $ de solde.
_CREDIT_KEYWORDS = (
    "exhausted balance", "insufficient balance", "balance is too low",
    "insufficient credit", "insufficient funds", "top up your", "topup",
    "payment required", "402", "purchase credits", "billing_hard_limit",
    "insufficient_quota", "exceeded your current quota", "not enough credit",
    # Distributeurs vidéo alternatifs (04/10/2026) : BytePlus suspend un
    # compte en impayé (« AccountOverdueError »), Runware nomme le manque de
    # crédit en un mot.
    "accountoverdue", "account overdue", "insufficientcredits",
)
#: Distributeurs vidéo autres que fal : une erreur de crédit qui les nomme
#: ne doit pas renvoyer l'utilisateur vers fal.ai.
_ALT_DISTRIBUTORS = (("byteplus", "BytePlus"), ("runware", "Runware"), ("piapi", "PiAPI"))
# Ce qui signe une erreur du fournisseur IA TEXTE (traduction, analyse
# d'image, composition) et non de fal.ai.
_TEXT_AI_MARKERS = (
    "anthropic", "plans & billing", "openai", "mistral", "insufficient_quota",
    "exceeded your current quota", "x-api-key", "console.anthropic",
)


def is_credit_error(err: str) -> bool:
    low = (err or "").lower()
    return any(kw in low for kw in _CREDIT_KEYWORDS)


def is_text_ai_error(err: str) -> bool:
    """L'erreur vient du fournisseur IA texte (Anthropic/OpenAI…), pas de fal."""
    low = (err or "").lower()
    return any(m in low for m in _TEXT_AI_MARKERS)


def fal_error_detail(err: str) -> str:
    """Le ou les `msg` d'un détail de validation fal (liste JSON-like
    `[{'loc': [...], 'msg': '…'}]`), sinon l'erreur elle-même, courte. Ce que
    fal reproche au clip (durée, résolution, taille) doit se LIRE, pas se
    deviner (« durée trop courte ? »)."""
    import re as _re
    msgs = _re.findall(r"""['"]msg['"]\s*:\s*['"]([^'"]{3,200})['"]""", err or "")
    if msgs:
        return " · ".join(dict.fromkeys(m.strip() for m in msgs))
    return (err or "").strip().replace("\n", " ")[:200]


# Refus par le FILTRE DE CONTENU d'un moteur (relevé du compte fal, 25/09/2026 :
# Seedance 2.0 → HTTP 422 `content_policy_violation`, « likenesses of real
# people », raison `partner_validation_failed` = filtre de ByteDance). Relancer
# ne sert à rien (fal classe l'erreur non rejouable) et peut être facturé.
_CONTENT_POLICY_MARKERS = (
    "content_policy_violation", "content policy", "partner_validation_failed",
    "likenesses of real people", "privacyinformation", "sensitivecontentdetected",
    "may contain real person",
    # BytePlus (codes « InputImageSensitiveContentDetected.PrivacyInformation »,
    # « OutputVideoSensitiveContentDetected.PolicyViolation ») est couvert par
    # « sensitivecontentdetected » ; les revendeurs parlent de modération.
    "content moderation", "contentmoderation", "policyviolation",
)
# « partner_validation_failed » n'en fait PLUS partie : c'est la raison
# générique du contrôle ByteDance, qui porte aussi les refus pour droits
# d'auteur (`cause: copyright`, Seedance 2.5, 03/10/2026) — ceux-là
# s'affichaient « visages de personnes réelles ».
_REAL_PERSON_MARKERS = (
    "likenesses of real people", "privacyinformation",
    "may contain real person", "real person",
)


def is_content_policy_error(err: str) -> bool:
    low = (err or "").lower()
    return any(m in low for m in _CONTENT_POLICY_MARKERS)


def is_real_person_refusal(err: str) -> bool:
    """Refus pour visage / ressemblance d'une personne réelle."""
    low = (err or "").lower()
    return is_content_policy_error(err) and any(m in low for m in _REAL_PERSON_MARKERS)


def content_policy_cause(err: str) -> str:
    """Cause déclarée par le filtre (`ctx.extra_info.cause`, ex. « copyright »),
    ou "" si fal n'en donne pas."""
    import re as _re
    m = _re.search(r"""['"]cause['"]\s*:\s*['"]([\w\- ]{2,40})['"]""", err or "")
    if m:
        return m.group(1).strip().lower()
    # Repli sur le MESSAGE du filtre seulement : l'erreur fal recopie aussi le
    # prompt envoyé, où le mot « copyright » peut figurer sans être la cause.
    return "copyright" if "copyright" in fal_error_detail(err).lower() else ""


def refused_after_generation(err: str) -> bool:
    """Le filtre a jugé la vidéo PRODUITE (le calcul a eu lieu), pas l'entrée."""
    low = (err or "").lower()
    return ("generated_video" in low or "generated output" in low
            or "outputvideosensitivecontentdetected" in low)


def content_policy_message(err: str, engine_label: str = "") -> str:
    """Refus de filtre, lisible : QUI refuse, POURQUOI, et quoi faire à la place."""
    from core.i18n import translate as _t
    eng = (engine_label or "").strip() or _t("Le moteur")
    if is_real_person_refusal(err):
        return " ".join([
            eng, _t("a refusé ce clip : visages de personnes réelles."),
            _t("C'est le filtre du propriétaire du modèle (ByteDance pour Seedance), le "
               "même chez tous les distributeurs : fal.ai n'est pas en cause."),
            _t("Pour garder vos acteurs : « Changer le décor · acteurs intacts », "
               "HappyHorse, Kling O3 ou Wan 2.7."),
        ])
    if content_policy_cause(err) == "copyright":
        return " ".join([
            eng, _t("a refusé la vidéo générée : ressemblance possible avec une œuvre "
                    "protégée (droits d'auteur)."),
            _t("C'est le contrôle du propriétaire du modèle (ByteDance pour Seedance), "
               "appliqué à l'image produite et non au prompt ; il n'est pas déterministe."),
            _t("Écartez ce qui évoque une œuvre connue (scène de film célèbre, "
               "personnage, marque, logo), puis relancez."),
        ])
    msg = f"{eng} {_t('a refusé ce clip (filtre de contenu) :')} {fal_error_detail(err)}"
    if refused_after_generation(err):
        msg += " " + _t("(refus prononcé sur la vidéo produite, après le calcul)")
    return msg


def humanize_api_error(err: str) -> str:
    """Erreur d'un worker de génération, lisible : nomme le BON compte quand
    c'est une affaire de crédits, laisse passer tout le reste tel quel."""
    if is_credit_error(err):
        if is_text_ai_error(err):
            return (
                "Crédits du fournisseur IA TEXTE (Anthropic/OpenAI…) épuisés — la "
                "préparation du prompt (traduction, analyse d'image, composition) a "
                "échoué. Le compte fal.ai n'est pas en cause.\n"
                "Rechargez ce compte (console.anthropic.com → Plans & Billing) ou "
                "changez de fournisseur dans Paramètres → Assistant IA."
            )
        low = (err or "").lower()
        if "relais fal" not in low:
            for _key, _name in _ALT_DISTRIBUTORS:
                if _key in low:
                    return (
                        f"Crédits {_name} insuffisants — la génération n'a pas pu "
                        f"démarrer. Rechargez votre compte {_name}, ou choisissez un "
                        f"autre distributeur dans le Studio.\n"
                        f"({fal_error_detail(err)})"
                    )
        return (
            "Crédits fal.ai insuffisants — la génération n'a pas pu démarrer.\n"
            "Rechargez votre compte sur fal.ai/dashboard pour continuer.\n"
            f"({fal_error_detail(err)})"
        )
    return err


class GenerationWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    def __init__(self, params: dict):
        super().__init__()
        self.params = params
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        # Bascule automatiquement sur la vraie API si une clé est configurée —
        # celle de fal OU celle du distributeur qui servira ce moteur (avant le
        # 04/10/2026, une clé BytePlus seule laissait PANDORA en simulation).
        try:
            from core.media_provider import real_generation_possible
            has_key = real_generation_possible(self.params.get("model", "seedance-2.0"))
        except Exception as e:
            self.failed.emit(f"Impossible de charger la configuration : {e}")
            return

        try:
            if has_key:
                from api.real import run_real as runner
            else:
                from api.mock import run_mock as runner
        except ImportError as e:
            pkg = "fal-client" if "fal" in str(e).lower() else str(e)
            self.failed.emit(
                f"Module manquant : {pkg}\n"
                "Installe les dépendances : pip install fal-client"
            )
            return

        try:
            result = runner(self.params, self.progress.emit, lambda: self._cancelled)
            if not self._cancelled:
                self.finished.emit(result)
        except Exception as e:
            if not self._cancelled:
                self.failed.emit(humanize_api_error(str(e)))
