"""
Utilitaire de traduction — traduit un prompt vers l'anglais avant envoi aux APIs.

Les prompts sont rédigés et optimisés dans la langue de l'utilisateur (français,
etc.) pour qu'il puisse les lire et corriger. Cette fonction est appelée juste
avant chaque appel réseau (Nano Banana, Seedance) pour convertir en anglais.
"""


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

    from core.config import load_config
    key = load_config().get("anthropic_key", "").strip()
    if not key:
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
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=800,
            system=(
                "You are a translator specializing in AI video generation prompts. "
                "Translate the input text into English, preserving all technical details, "
                "descriptive adjectives, proper nouns, and prompt structure exactly. "
                "If the text is already in English, return it unchanged. "
                "Tokens of the form §D0§, §D1§, §D2§ … are protected placeholders for "
                "spoken dialogue or text-on-object — copy them exactly as-is. "
                "Return ONLY the translated text. No explanation, no prefix."
            ),
            messages=[{"role": "user", "content": safe}],
        )
        result = msg.content[0].text.strip()
    except Exception:
        return text

    # ── Restaure les dialogues originaux ─────────────────────────────────────
    def _restore(m: re.Match) -> str:
        idx = int(m.group(1))
        return protected[idx] if idx < len(protected) else m.group(0)

    result = re.sub(r"§D(\d+)§", _restore, result)
    return result


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

    from core.config import load_config
    key = load_config().get("anthropic_key", "").strip()
    if not key:
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
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=800,
            system=(
                "You are a translator specializing in AI video generation prompts. "
                "Translate the input text into Simplified Chinese (Mandarin), "
                "preserving all technical details, descriptive adjectives, "
                "proper nouns, and prompt structure exactly. "
                "Tokens of the form §D0§, §D1§, §D2§ … are protected placeholders — "
                "copy them exactly as-is without any modification. "
                "Return ONLY the translated text. No explanation, no prefix."
            ),
            messages=[{"role": "user", "content": safe}],
        )
        result = msg.content[0].text.strip()
    except Exception:
        return text

    # ── Restaure les dialogues originaux ─────────────────────────────────────
    def _restore(m: re.Match) -> str:
        idx = int(m.group(1))
        return protected[idx] if idx < len(protected) else m.group(0)

    result = re.sub(r"§D(\d+)§", _restore, result)
    return result
