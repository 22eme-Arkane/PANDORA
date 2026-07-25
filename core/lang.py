"""
Utilitaire de traduction — traduit un prompt vers l'anglais avant envoi aux APIs.

Les prompts sont rédigés et optimisés dans la langue de l'utilisateur (français,
etc.) pour qu'il puisse les lire et corriger. Cette fonction est appelée juste
avant chaque appel réseau (Nano Banana, Seedance) pour convertir en anglais.
"""

import re



# ── Langue des dialogues (colonne « Langues » du storyboard) ────────────────────
# La langue choisie par plan ne modifie JAMAIS le prompt affiché : à l'ENVOI vers
# Seedance, seuls les dialogues entre guillemets sont traduits vers cette langue.
# Anglais = défaut recommandé (meilleur lipsync Seedance 2.0).
DIALOGUE_LANGS = [
    ("Anglais  (recommandé)", "en"),
    ("Français",              "fr"),
    ("Espagnol",              "es"),
    ("Allemand",              "de"),
    ("Italien",               "it"),
    ("Portugais",             "pt"),
    ("Japonais",              "ja"),
    ("Chinois (mandarin)",    "zh"),
    ("Coréen",                "ko"),
    ("Russe",                 "ru"),
    ("Arabe",                 "ar"),
]
_LANG_NAMES = {
    "en": "English", "fr": "French", "es": "Spanish", "de": "German",
    "it": "Italian", "pt": "Portuguese", "ja": "Japanese",
    "zh": "Simplified Chinese (Mandarin)", "ko": "Korean", "ru": "Russian",
    "ar": "Arabic",
}


def lang_label(code: str) -> str:
    """Libellé court d'un code langue pour l'affichage (cellule du tableau)."""
    for label, c in DIALOGUE_LANGS:
        if c == code:
            return label.split("  ")[0]   # « Anglais » sans le « (recommandé) »
    return "Anglais"


# Marqueurs d'une réponse CONVERSATIONNELLE du modèle (refus, demande de
# précision, préambule) au lieu d'une réplique traduite.
_CHATTY_MARKERS = (
    "i'd be happy", "i would be happy", "could you provide", "could you clarify",
    "i can't", "i cannot", "i'm unable", "please provide", "as an ai",
    "appears to be", "it seems", "sorry", "désolé", "je peux", "note:",
    "translation:", "traduction :", "here is", "voici la",
)


def _looks_conversational(out: str, source: str) -> bool:
    """La sortie ressemble-t-elle à une RÉPONSE du modèle plutôt qu'à une réplique ?

    Sans ce filet, un refus ou une demande de précision était injecté tel quel dans
    le prompt final — c'est ainsi qu'un « I'd be happy to help translate movie
    dialogue, but "brrrrrrr" appears to be a sound effect… Could you provide: 1. … »
    s'est retrouvé DANS le prompt envoyé au moteur vidéo (constat Matthieu
    2026-07-25). En cas de doute on garde la réplique d'origine : une réplique non
    traduite est bénigne, une réponse de chatbot dans le prompt ne l'est pas."""
    o = (out or "").strip()
    if not o:
        return True
    low = o.lower()
    if any(m in low for m in _CHATTY_MARKERS):
        return True
    # Une réplique de film ne contient pas de liste numérotée ni de saut de ligne.
    if "\n" in o or re.search(r"(?m)^\s*\d+[.)]\s", o):
        return True
    # Réponse anormalement plus longue que la réplique d'origine.
    src = (source or "").strip()
    if len(o) > max(120, len(src) * 3 + 40):
        return True
    return False


def translate_dialogues_to(text: str, lang: str) -> str:
    """Traduit UNIQUEMENT les dialogues entre guillemets (« », “ ”, " ", ‘ ’,
    ' ') vers `lang`, en conservant les guillemets. Le reste du texte est laissé
    intact. Appelé à l'ENVOI vers Seedance — le prompt à l'écran n'est jamais
    modifié. No-op si pas de guillemets, langue inconnue ou clé Anthropic absente."""
    if not text or not text.strip():
        return text
    target = _LANG_NAMES.get((lang or "en").lower())
    if not target:
        return text
    from core.ai_provider import complete, key_error
    if key_error():
        return text

    import re
    # Apostrophes : une ' collée à une lettre (contraction anglaise « It's »,
    # élision française « l'arme ») n'ouvre/ferme PAS un dialogue — sinon
    # « It's dark. The killer's knife » devenait une fausse réplique traduite.
    pat = re.compile(
        r"«[^»]*»|“[^”]{1,300}”|‘[^’]{1,300}’|\"[^\"]{1,300}\""
        r"|(?<![A-Za-zÀ-ÿ])'[^']{1,300}'(?![A-Za-zÀ-ÿ])"
    )
    # Les NOMS D'ENTITÉS du bloc [COHÉRENCE VISUELLE] sont entre guillemets droits
    # (Personnage "Jésus", Décor "Canyon désertique de Bethléem"…). Ce ne sont pas
    # des répliques : les traduire renommait le décor et le personnage dans le bloc
    # de cohérence (2026-07-24). On les masque le temps de la traduction.
    _entity_line = re.compile(
        r"^\s*(?:Personnage|D[ée]cor|Accessoire|V[ée]hicule|HMC|Costume)[^\n]*$",
        re.MULTILINE | re.IGNORECASE)
    _kept: list[str] = []

    def _mask(m: re.Match) -> str:
        _kept.append(m.group(0))
        return f"\x00E{len(_kept) - 1}\x00"

    text = _entity_line.sub(_mask, text)
    memo: dict[str, str] = {}

    def _tr(m: re.Match) -> str:
        seg = m.group(0)
        inner = seg[1:-1].strip()
        if not inner:
            return seg
        if seg in memo:
            return memo[seg]
        try:
            out = complete(
                (f"Translate the following spoken movie dialogue line into {target}. "
                 "Keep it natural, spoken, faithful to the meaning and tone.\n"
                 "If the line is an onomatopoeia, a vocal sound effect, a proper "
                 "noun or is already in the target language, return it UNCHANGED.\n"
                 "NEVER ask a question, never explain, never apologise, never add "
                 "notes: reply with the line and nothing else.\n"
                 "Return ONLY the line — no quotes, no notes, no prefix."),
                inner, tier="utility", max_tokens=300, task="translate",
            ).strip()
        except Exception:
            return seg
        out = out.strip().strip("«»“”‘’\"'").strip()
        if not out:
            return seg
        # FILET : une réponse conversationnelle du modèle ne doit JAMAIS entrer
        # dans le prompt (voir _looks_conversational).
        if _looks_conversational(out, inner):
            return seg
        res = seg[0] + out + seg[-1]
        memo[seg] = res
        return res

    out_text = pat.sub(_tr, text)
    # Restaure les lignes d'entités masquées (jamais traduites).
    for _i, _line in enumerate(_kept):
        out_text = out_text.replace(f"\x00E{_i}\x00", _line)
    return out_text


def translate_to_english_ex(text: str) -> tuple:
    """Comme translate_to_english, mais retourne (texte, raison_d_echec).

    La raison est HUMANISÉE (« Crédits API épuisés… ») : sans elle, un échec de
    facturation ressemblait à un bug de l'application — le prompt repartait en
    français avec pour seule explication « moteur de traduction indisponible »
    (constat Matthieu 2026-07-25, crédit Anthropic à zéro)."""
    global _LAST_TRANSLATE_ERROR
    _LAST_TRANSLATE_ERROR = ""
    out = translate_to_english(text)
    return out, _LAST_TRANSLATE_ERROR


_LAST_TRANSLATE_ERROR = ""


def translate_to_english(text: str) -> str:
    """
    Traduit le texte en anglais via Claude Haiku.
    Si le texte est déjà en anglais, le retourne tel quel.

    Les dialogues (entre « », “ ” ou ‘ ’) sont remplacés par des marqueurs
    §D0§, §D1§… avant l'appel, puis restaurés ensuite — ce qui garantit
    qu'ils restent dans leur langue d'origine même si Claude oublie les consignes.

    En cas d'erreur ou de clé Anthropic manquante, retourne le texte original.
    """
    if not text or not text.strip():
        return text

    # Skip translation when app is already in English — prompt is written in English directly
    try:
        from core.i18n import get_lang
        if get_lang() == "en":
            return text
    except Exception:
        pass

    global _LAST_TRANSLATE_ERROR
    _LAST_TRANSLATE_ERROR = ""
    from core.ai_provider import complete, key_error
    # Clé de la TÂCHE « translate » (et non du moteur global) : l'appel plus bas
    # utilise task="translate", donc tester le moteur global court-circuitait la
    # traduction quand seul le moteur de tâche est configuré — le prompt partait
    # alors EN FRANÇAIS au moteur vidéo (constat Matthieu 2026-07-24).
    _ke = key_error(task="translate")
    if _ke:
        _LAST_TRANSLATE_ERROR = _ke
        return text

    import re

    # ── Extrait et protège les dialogues par des marqueurs ───────────────────
    protected: list[str] = []

    def _protect(m: re.Match) -> str:
        idx = len(protected)
        protected.append(m.group(0))
        return f"§D{idx}§"

    safe = re.sub(r"«[^»]*»", _protect, text)
    safe = re.sub(r"“[^”]{1,300}”", _protect, safe)
    safe = re.sub(r"‘[^’]{1,300}’", _protect, safe)

    try:
        result = complete(
            (
                "You are a translator specializing in AI video generation prompts. "
                "Translate the input text into English, preserving all technical details, "
                "descriptive adjectives, proper nouns, and prompt structure exactly. "
                "If the text is already in English, return it unchanged. "
                "Tokens of the form §D0§, §D1§, §D2§ … are protected placeholders for "
                "spoken dialogue or text-on-object — copy them exactly as-is. "
                "Return ONLY the translated text. No explanation, no prefix."
            ),
            # 4000 tokens : 800 tronquait les prompts longs (un prompt final
            # assemble depasse 2000 caracteres) -> traduction coupee net.
            safe, tier="utility", max_tokens=4000, task="translate",
        ).strip()
    except Exception as e:
        # On MEMORISE la vraie cause (credits epuises, quota, cle invalide...) :
        # sans elle, l'appelant ne peut que dire « indisponible » et l'utilisateur
        # cherche un bug dans l'app alors qu'il s'agit de sa facturation.
        try:
            from core.ai_provider import humanize_ai_error
            _LAST_TRANSLATE_ERROR = humanize_ai_error(str(e))
        except Exception:
            _LAST_TRANSLATE_ERROR = str(e)[:200]
        return text

    # ── Restaure les dialogues originaux ─────────────────────────────────────
    def _restore(m: re.Match) -> str:
        idx = int(m.group(1))
        return protected[idx] if idx < len(protected) else m.group(0)

    result = re.sub(r"§D(\d+)§", _restore, result)
    return result


def translate_to_french(text: str) -> str:
    """Traduit le texte en français via Claude Haiku — pour AFFICHER en français un
    prompt stocké en anglais (ex. édition d'une variation de décor). Protège les
    dialogues (§D…§) comme translate_to_english. Retourne le texte original en cas
    d'erreur / clé manquante / texte déjà français."""
    if not text or not text.strip():
        return text

    from core.ai_provider import complete, key_error
    if key_error():
        return text

    import re
    protected: list[str] = []

    def _protect(m: "re.Match") -> str:
        idx = len(protected)
        protected.append(m.group(0))
        return f"§D{idx}§"

    safe = re.sub(r"«[^»]*»", _protect, text)
    safe = re.sub(r"“[^”]{1,300}”", _protect, safe)
    safe = re.sub(r"‘[^’]{1,300}’", _protect, safe)

    try:
        result = complete(
            (
                "You are a translator specializing in AI video/image generation prompts. "
                "Translate the input text into FRENCH (français), preserving all technical "
                "details, descriptive adjectives, proper nouns and prompt structure exactly. "
                "If the text is already in French, return it unchanged. "
                "Tokens of the form §D0§, §D1§ … are protected placeholders — copy them "
                "exactly as-is. Return ONLY the translated text. No explanation, no prefix."
            ),
            # 4000 tokens : 800 tronquait les prompts longs (un prompt final
            # assemble depasse 2000 caracteres) -> traduction coupee net.
            safe, tier="utility", max_tokens=4000, task="translate",
        ).strip()
    except Exception:
        return text

    def _restore(m: "re.Match") -> str:
        idx = int(m.group(1))
        return protected[idx] if idx < len(protected) else m.group(0)

    return re.sub(r"§D(\d+)§", _restore, result)


def translate_to_chinese(text: str) -> str:
    """
    Traduit le texte en mandarin simplifié via Claude Haiku.
    Utilisé comme fallback de compression quand le prompt anglais est trop long
    (le chinois est ~3× plus compact pour la même information).

    Les dialogues (entre « », “ ” ou ‘ ’) sont remplacés par des
    marqueurs §D0§, §D1§… avant l'appel, puis restaurés ensuite — ce qui
    garantit qu'ils ne sont jamais traduits, même si Claude oublie les consignes.

    En cas d'erreur ou de clé Anthropic manquante, retourne le texte original.
    """
    if not text or not text.strip():
        return text

    from core.ai_provider import complete, key_error
    if key_error():
        return text

    import re

    # ── Extrait et protège les dialogues par des marqueurs ───────────────────
    protected: list[str] = []

    def _protect(m: re.Match) -> str:
        idx = len(protected)
        protected.append(m.group(0))
        return f"§D{idx}§"

    # Guillemets français « … »
    safe = re.sub(r"«[^»]*»", _protect, text)
    # Guillemets anglais doubles " … " (sans englober plusieurs répliques)
    safe = re.sub(r"“[^”]{1,300}”", _protect, safe)
    # Guillemets anglais simples typographiques ' … '
    safe = re.sub(r"‘[^’]{1,300}’", _protect, safe)

    try:
        result = complete(
            (
                "You are a translator specializing in AI video generation prompts. "
                "Translate the input text into Simplified Chinese (Mandarin), "
                "preserving all technical details, descriptive adjectives, "
                "proper nouns, and prompt structure exactly. "
                "Tokens of the form §D0§, §D1§, §D2§ … are protected placeholders — "
                "copy them exactly as-is without any modification. "
                "Return ONLY the translated text. No explanation, no prefix."
            ),
            # 4000 tokens : 800 tronquait les prompts longs (un prompt final
            # assemble depasse 2000 caracteres) -> traduction coupee net.
            safe, tier="utility", max_tokens=4000, task="translate",
        ).strip()
    except Exception:
        return text

    # ── Restaure les dialogues originaux ─────────────────────────────────────
    def _restore(m: re.Match) -> str:
        idx = int(m.group(1))
        return protected[idx] if idx < len(protected) else m.group(0)

    result = re.sub(r"§D(\d+)§", _restore, result)
    return result
