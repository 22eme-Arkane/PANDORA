"""core/speech_engines.py — Registre des moteurs de voix de synthèse (fal.ai).

Un moteur, ce n'est pas seulement un point d'entrée : c'est aussi la FAÇON de
lui parler. Les schémas fal divergent sur trois points qui, mal renseignés,
font échouer l'appel ou produisent une voix anglaise lisant du français :

  - le nom du champ texte : ``text``, ``prompt`` ou ``transcript`` ;
  - l'emplacement de la voix : à plat (``voice``) ou imbriqué
    (``voice_setting.voice_id``, ``voice.name``) ;
  - le nom ET la valeur de la langue : ``language`` / ``language_code`` /
    ``language_boost``, avec des valeurs qui vont de ``fr`` à
    ``French (France)``.

C'est exactement ce qui manquait : l'ancien appel envoyait ``{"text": …}`` à
tout le monde. Trois moteurs le refusaient (champ requis ``prompt``), et les
autres tombaient sur leur voix par défaut — ``Rachel`` chez ElevenLabs,
``Craig (en)`` chez Inworld — d'où le « français mal géré ».

Relevé sur les schémas OpenAPI de fal le **2026-08-19**. Aucun appel n'a été
exécuté pour l'établir : ce fichier décrit ce que les schémas déclarent, pas
ce qu'un rendu réel donne. Les points non vérifiés sont dans ``note``.

Ce module est pur (aucun import réseau ni Qt) pour rester testable seul.
"""

from __future__ import annotations

import re

# ── Marqueur de voix francophone ─────────────────────────────────────────────
# Inworld suffixe ses voix par la langue — « Alain (fr) » ; ByteDance encode la
# couverture dans le nom — « usseau_fr ». Une voix sans marqueur n'est PAS
# présumée francophone : le doute profite au silence, pas à l'étiquette.
_FR_TAG = re.compile(r"\(fr\)|_fr$|^fr[-_]", re.IGNORECASE)


def _is_fr(voice: str, explicit: list[str] | None) -> bool:
    if explicit is not None:
        return voice in explicit
    return bool(_FR_TAG.search(voice))


# ── Catalogues de voix ───────────────────────────────────────────────────────

# Inworld TTS-1.5 Max — 113 voix, 4 francophones natives.
_INWORLD_VOICES = [
    "Alain (fr)", "Hélène (fr)", "Mathieu (fr)", "Étienne (fr)",
    "Loretta (en)", "Darlene (en)", "Marlene (en)", "Hank (en)", "Evelyn (en)",
    "Celeste (en)", "Pippa (en)", "Tessa (en)", "Liam (en)", "Callum (en)",
    "Hamish (en)", "Abby (en)", "Graham (en)", "Rupert (en)", "Mortimer (en)",
    "Snik (en)", "Anjali (en)", "Saanvi (en)", "Arjun (en)", "Claire (en)",
    "Oliver (en)", "Simon (en)", "Elliot (en)", "James (en)", "Serena (en)",
    "Gareth (en)", "Vinny (en)", "Lauren (en)", "Jessica (en)", "Ethan (en)",
    "Tyler (en)", "Jason (en)", "Chloe (en)", "Veronica (en)", "Victoria (en)",
    "Miranda (en)", "Sebastian (en)", "Victor (en)", "Malcolm (en)",
    "Kayla (en)", "Nate (en)", "Jake (en)", "Brian (en)", "Amina (en)",
    "Kelsey (en)", "Derek (en)", "Grant (en)", "Evan (en)", "Alex (en)",
    "Ashley (en)", "Craig (en)", "Deborah (en)", "Dennis (en)", "Edward (en)",
    "Elizabeth (en)", "Hades (en)", "Julia (en)", "Pixie (en)", "Mark (en)",
    "Olivia (en)", "Priya (en)", "Ronald (en)", "Sarah (en)", "Shaun (en)",
    "Theodore (en)", "Timothy (en)", "Wendy (en)", "Dominus (en)", "Hana (en)",
    "Clive (en)", "Carter (en)", "Blake (en)", "Luna (en)",
    "Yichen (zh)", "Xiaoyin (zh)", "Xinyi (zh)", "Jing (zh)",
    "Erik (nl)", "Katrien (nl)", "Lennart (nl)", "Lore (nl)",
    "Johanna (de)", "Josef (de)", "Gianni (it)", "Orietta (it)",
    "Asuka (ja)", "Satoshi (ja)",
    "Hyunwoo (ko)", "Minji (ko)", "Seojun (ko)", "Yoona (ko)",
    "Szymon (pl)", "Wojciech (pl)", "Heitor (pt)", "Maitê (pt)",
    "Diego (es)", "Lupita (es)", "Miguel (es)", "Rafael (es)",
    "Svetlana (ru)", "Elena (ru)", "Dmitry (ru)", "Nikolai (ru)",
    "Riya (hi)", "Manoj (hi)", "Yael (he)", "Oren (he)",
    "Nour (ar)", "Omar (ar)",
]

# ElevenLabs — voix du catalogue de base. La colonne FR reprend celle déjà
# utilisée par l'onglet Turbo v2.5 (api/tts.py), pour ne pas dire deux choses
# différentes du même moteur dans la même page.
_ELEVEN_VOICES = [
    "Charlotte", "River", "Alice", "Matilda", "Sarah", "Laura",
    "Aria", "Jessica", "Lily", "Callum", "Daniel", "George",
    "Brian", "Charlie", "Chris", "Eric", "Liam", "Roger", "Will", "Bill",
]
_ELEVEN_FR = ["Charlotte", "River", "Alice", "Matilda", "Lily",
              "Daniel", "George", "Brian"]

# MiniMax — voix « système ». Elles ne portent pas de langue : c'est
# language_boost qui fait le travail.
_MINIMAX_VOICES = [
    "Wise_Woman", "Friendly_Person", "Inspirational_girl", "Deep_Voice_Man",
    "Calm_Woman", "Casual_Guy", "Lively_Girl", "Patient_Man", "Young_Knight",
    "Determined_Man", "Lovely_Girl", "Decent_Boy", "Imposing_Manner",
    "Elegant_Man", "Abbess", "Sweet_Girl_2", "Exuberant_Girl",
]

# ByteDance Seed Speech v2 — le suffixe encode les langues couvertes.
_SEED_VOICES = [
    "usseau_fr",
    "stokie_en", "dacey_en", "tim_en",
    "kian_en_zh", "cedric_en_zh", "sophie_en_zh", "jean_en_zh", "magnus_en_zh",
    "mabel_en_zh", "nadia_en_zh", "opal_en_zh", "pearl_en_zh", "quentin_en_zh",
    "vienna_mixed_en_zh", "alina_mixed_en_zh", "corinne_mixed_en_zh",
    "esther_mixed_en_zh", "freya_mixed_en_zh", "gigi_mixed_en_zh",
    "holly_mixed_en_zh", "lyla_mixed_en_zh", "daisy_mixed_en_zh",
    "vivi_mixed_en_zh_ja_es_id", "mindy_en_es_id_pt_zh",
    "jess_ja_es_id_pt_en_zh", "pinky_es_ko_mixed_en_zh", "sandy_es_mixed_en_zh",
    "tracy_es_zh", "sweety_ja_es", "sven_de", "minimi_ja", "felipe_es",
    "han_id", "martins_pt", "enzo_it", "shane_ko",
    "bonnie_zh", "felix_zh", "celeste_zh", "monkey_king_zh",
]

# Gemini 3.1 Flash TTS — 30 voix, toutes multilingues (la langue se choisit à
# part). Noms d'étoiles.
_GEMINI_VOICES = [
    "Achernar", "Achird", "Algenib", "Algieba", "Alnilam", "Aoede", "Autonoe",
    "Callirrhoe", "Charon", "Despina", "Enceladus", "Erinome", "Fenrir",
    "Gacrux", "Iapetus", "Kore", "Laomedeia", "Leda", "Orus", "Pulcherrima",
    "Puck", "Rasalgethi", "Sadachbia", "Sadaltager", "Schedar", "Sulafat",
    "Umbriel", "Vindemiatrix", "Zephyr", "Zubenelgenubi",
]

# Qwen3-TTS 1.7B.
_QWEN3_VOICES = ["Vivian", "Serena", "Uncle_Fu", "Dylan", "Eric", "Ryan",
                 "Aiden", "Ono_Anna", "Sohee"]

# Qwen Audio 3.0 TTS — 45 voix. fal ne publie PAS la couverture par voix (elle
# est sur le site Alibaba, inaccessible depuis ici) : aucune n'est donc marquée
# francophone. Le paramètre `language` reste le levier fiable.
_QWEN_AUDIO3_VOICES = [
    "Cherry", "Serena", "Ethan", "Chelsie", "Momo", "Vivian", "Moon", "Maia",
    "Kai", "Nofish", "Bella", "Jennifer", "Ryan", "Katerina", "Aiden", "Mia",
    "Mochi", "Bellona", "Vincent", "Bunny", "Neil", "Elias", "Arthur", "Nini",
    "Seren", "Pip", "Stella", "Bodega", "Sonrisa", "Alek", "Dolce", "Sohee",
    "Lenn", "Emilien", "Andre", "Jada", "Dylan", "Li", "Marcus", "Roy",
    "Peter", "Sunny", "Eric", "Rocky", "Kiki",
]

# Async TTS Pro — 100 voix, moteur restreint à 6 langues européennes dont le
# français : chaque voix est censée les couvrir toutes.
_ASYNC_VOICES = [
    "Jennie", "Stella", "Max", "Hayes", "Elara", "Cleo", "Fisher", "Corin",
    "Thaddeus", "Lucina", "Acadia", "Huxley", "Winslet", "Jethro", "Elio",
    "Rupert", "Eira", "Nyra", "Arian", "Lily", "Pierce", "Kaela", "Elowen",
    "Freya", "Lenny", "Alessa", "Pandora", "Fia", "Abbott", "Kael", "Orla",
    "Sable", "Marnie", "Sera", "Virel", "Liora", "Riven", "Elys", "Dreena",
    "Rhea", "Vela", "Nymera", "Isolde", "Lirien", "Zella", "Avenna", "Mirelle",
    "Calia", "Lunea", "Lucan", "Tarian", "Arlo", "Jovan", "Neron", "Ziven",
    "Dax", "Orien", "Lior", "Eryx", "Tyren", "Nox", "Elric", "Varian", "Zoran",
    "Miro", "Dalen", "Ronix", "Jarek", "Nyxie", "Soren", "Viona", "Selene",
    "Rachiel", "Corbin", "Abigail", "Faith", "Kimberly", "Dave", "Grace",
    "Alden", "Renly", "Violet", "Joel", "Xavier", "Esmeralda", "Robert",
    "Lila", "Brooks", "Lennox", "Vanessa", "Simon", "Nyomi", "Jack",
    "Penelope", "Brayden", "Abel", "Nellie", "Connie", "Andrew", "Lincoln",
]

# xAI TTS — 5 voix, décrites par leur caractère et non par une langue.
_XAI_VOICES = ["eve", "ara", "rex", "sal", "leo"]


# ── Registre ─────────────────────────────────────────────────────────────────
# text_key   : nom du champ texte attendu (un mauvais nom = rejet 422)
# voice_key  : chemin où déposer la voix ; "a.b" = imbriqué
# lang_key   : nom du champ langue ; lang_fr = sa valeur pour le français
# fr_voices  : liste explicite, ou None → déduite du marqueur dans le nom

ENGINES: dict[str, dict] = {
    "inworld": {
        "label":       "Inworld TTS-1.5 Max  ·  4 voix FR natives  ·  $0.01/1000c",
        "endpoint":    "fal-ai/inworld-tts",
        "text_key":    "text",
        "voice_key":   "voice",
        "lang_key":    "",           # le moteur n'expose aucun champ de langue :
        "lang_fr":     "",           # la voix porte la langue à elle seule.
        "voices":      _INWORLD_VOICES,
        "fr_voices":   None,
        "price":       "$0.01 / 1000 c",
        "price_per_1k": 0.01,
        "note": "Alain, Hélène, Mathieu et Étienne sont des voix françaises "
                "natives — pas des voix anglaises lisant du français.",
    },
    "elevenlabs-v3": {
        "label":       "ElevenLabs Eleven v3  ·  voix FR/EN  ·  $0.10/1000c",
        "endpoint":    "fal-ai/elevenlabs/tts/eleven-v3",
        "text_key":    "text",
        "voice_key":   "voice",
        "lang_key":    "language_code",
        "lang_fr":     "fr",
        "voices":      _ELEVEN_VOICES,
        "fr_voices":   _ELEVEN_FR,
        "price":       "$0.10 / 1000 c",
        "price_per_1k": 0.10,
        "note": "Le moteur retombe sur « Rachel » (voix américaine) si aucune "
                "voix n'est transmise — c'était le cas jusqu'ici.",
    },
    "minimax-2.8-hd": {
        "label":       "MiniMax Speech 2.8 HD  ·  renfort FR  ·  $0.10/1000c",
        "endpoint":    "fal-ai/minimax/speech-2.8-hd",
        "text_key":    "prompt",
        "voice_key":   "voice_setting.voice_id",
        "lang_key":    "language_boost",
        "lang_fr":     "French",
        "voices":      _MINIMAX_VOICES,
        "fr_voices":   [],           # voix système, sans langue propre
        "price":       "$0.10 / 1000 c",
        "price_per_1k": 0.10,
        "note": "Attend « prompt » et non « text ». Les voix sont neutres : "
                "c'est language_boost qui impose le français.",
    },
    "minimax-2.8-turbo": {
        "label":       "MiniMax Speech 2.8 Turbo  ·  renfort FR  ·  $0.06/1000c",
        "endpoint":    "fal-ai/minimax/speech-2.8-turbo",
        "text_key":    "prompt",
        "voice_key":   "voice_setting.voice_id",
        "lang_key":    "language_boost",
        "lang_fr":     "French",
        "voices":      _MINIMAX_VOICES,
        "fr_voices":   [],
        "price":       "$0.06 / 1000 c",
        "price_per_1k": 0.06,
        "note": "Attend « prompt » et non « text ».",
    },
    "qwen-audio-3": {
        "label":       "Qwen Audio 3.0 TTS  ·  45 voix · FR explicite  ·  ~$0.05/1000c",
        "endpoint":    "alibaba/qwen-audio-3-tts",
        "text_key":    "text",
        "voice_key":   "voice",
        "lang_key":    "language",
        "lang_fr":     "French",
        "voices":      _QWEN_AUDIO3_VOICES,
        "fr_voices":   [],
        "price":       "~$0.05 / 1000 c",
        "price_per_1k": 0.05,
        "note": "Le plus récent du catalogue fal (29/07/2026). La couverture "
                "linguistique voix par voix n'est pas publiée par fal — "
                "essayer plusieurs voix avec la langue forcée sur French.",
    },
    "seed-speech-v2": {
        "label":       "ByteDance Seed Speech v2  ·  1 voix FR native  ·  tarif non relevé",
        "endpoint":    "fal-ai/bytedance/seed-speech/tts/v2",
        "text_key":    "text",
        "voice_key":   "voice",
        "lang_key":    "language",
        "lang_fr":     "fr",
        "voices":      _SEED_VOICES,
        "fr_voices":   None,          # « usseau_fr » détectée par le marqueur
        "price":       "tarif fal non relevé",
        "price_per_1k": 0.0,
        "note": "Accepte une consigne de jeu en langage naturel "
                "(voice_instruction) : « d'une voix lasse, plus lentement ».",
    },
    "async-tts-pro": {
        "label":       "Async TTS Pro  ·  6 langues dont FR · 100 voix  ·  $0.01/1000c",
        "endpoint":    "async/tts-pro/v1.0",
        "text_key":    "transcript",
        "voice_key":   "voice.name",
        "lang_key":    "language",
        "lang_fr":     "fr",
        "voices":      _ASYNC_VOICES,
        "fr_voices":   [],
        "price":       "$0.01 / 1000 c",
        "price_per_1k": 0.01,
        "note": "Moteur restreint à 6 langues européennes : le français y est "
                "traité comme une langue principale, pas comme la trentième.",
    },
    "gemini-tts": {
        "label":       "Gemini 3.1 Flash TTS  ·  FR (France)  ·  tarif non relevé",
        "endpoint":    "fal-ai/gemini-3.1-flash-tts",
        "text_key":    "prompt",
        "voice_key":   "voice",
        "lang_key":    "language_code",
        "lang_fr":     "French (France)",
        "voices":      _GEMINI_VOICES,
        "fr_voices":   [],
        "price":       "tarif fal non relevé",
        "price_per_1k": 0.0,
        "note": "Attend « prompt » et non « text ».",
    },
    "xai-tts": {
        "label":       "xAI TTS  ·  FR · balises expressives  ·  $0.015/1000c",
        "endpoint":    "xai/tts/v1",
        "text_key":    "text",
        "voice_key":   "voice",
        "lang_key":    "language",
        "lang_fr":     "fr",
        "voices":      _XAI_VOICES,
        "fr_voices":   [],
        "price":       "$0.015 / 1000 c",
        "price_per_1k": 0.015,
        "note": "Accepte des balises dans le texte : [laugh], [pause], "
                "<whisper>…</whisper>. Cinq voix seulement.",
    },
    "qwen3": {
        "label":       "Qwen3-TTS 1.7B  ·  FR · open source  ·  tarif non relevé",
        "endpoint":    "fal-ai/qwen-3-tts/text-to-speech/1.7b",
        "text_key":    "text",
        "voice_key":   "voice",
        "lang_key":    "language",
        "lang_fr":     "French",
        "voices":      _QWEN3_VOICES,
        "fr_voices":   [],
        "price":       "tarif fal non relevé",
        "price_per_1k": 0.0,
        "note": "",
    },
    "maya1": {
        "label":       "Maya1  ·  voix expressive · sans réglage",
        "endpoint":    "fal-ai/maya",
        "text_key":    "text",
        "voice_key":   "",           # aucun choix de voix exposé
        "lang_key":    "",
        "lang_fr":     "",
        "voices":      [],
        "fr_voices":   [],
        "price":       "~$0.002 / s",
        "price_per_1k": 0.0,
        "note": "N'expose ni voix ni langue : la langue est déduite du texte.",
    },
    # ── Hors menu : sert UNIQUEMENT aux extraits « Écouter » ──────────────────
    # L'onglet ElevenLabs Turbo v2.5 a son propre mode dans la page Doublage.
    # Il n'a rien à faire dans le menu multi-moteurs, mais son bouton « Écouter »
    # doit auditionner le vrai moteur — pas un cousin qui sonnerait autrement.
    # Ces champs sont confirmés par ElevenLabsWorker (api/tts.py), qui envoie
    # déjà text + voice + language_code à ce point d'entrée.
    "elevenlabs-turbo": {
        "label":       "ElevenLabs Turbo v2.5",
        "endpoint":    "fal-ai/elevenlabs/tts/turbo-v2.5",
        "text_key":    "text",
        "voice_key":   "voice",
        "lang_key":    "language_code",
        "lang_fr":     "fr",
        "voices":      _ELEVEN_VOICES,
        "fr_voices":   _ELEVEN_FR,
        "price":       "$0.05 / 1000 c",
        "price_per_1k": 0.05,
        "note": "",
    },
}

# Moteurs présents dans ENGINES mais volontairement absents du menu : ils
# existent pour que le bouton « Écouter » puisse auditionner le moteur réel
# d'un mode qui a déjà sa propre carte.
AUDITION_ONLY: set[str] = {"elevenlabs-turbo"}

# Ordre d'affichage — les moteurs réellement bons en français d'abord, pour que
# le premier essai d'un utilisateur soit le bon.
ORDER: list[str] = [
    "inworld", "elevenlabs-v3", "minimax-2.8-hd", "minimax-2.8-turbo",
    "qwen-audio-3", "seed-speech-v2", "async-tts-pro", "gemini-tts",
    "xai-tts", "qwen3", "maya1",
]

DEFAULT_ENGINE = "inworld"


def spec(key: str) -> dict:
    """Fiche d'un moteur. Une clé inconnue retombe sur le moteur par défaut
    plutôt que de lever : un projet enregistré avec un moteur retiré doit
    continuer de s'ouvrir."""
    return ENGINES.get(key) or ENGINES[DEFAULT_ENGINE]


def voices_for(key: str) -> list[tuple[str, str, bool]]:
    """Voix d'un moteur, francophones en tête → (libellé, valeur, est_fr)."""
    s = spec(key)
    explicit = s.get("fr_voices")
    out = [(v, v, _is_fr(v, explicit)) for v in s.get("voices", [])]
    out.sort(key=lambda t: (not t[2], s["voices"].index(t[1])))
    return out


def has_french_voices(key: str) -> bool:
    return any(is_fr for _, _, is_fr in voices_for(key))


def default_voice_for(key: str) -> str:
    """Première voix francophone si le moteur en a une, sinon sa première voix.
    Jamais de repli implicite du moteur : c'est ce silence qui faisait parler
    Rachel."""
    vs = voices_for(key)
    return vs[0][1] if vs else ""


def _put(d: dict, path: str, value) -> None:
    """Dépose une valeur, en créant les niveaux d'un chemin pointé."""
    parts = path.split(".")
    for p in parts[:-1]:
        d = d.setdefault(p, {})
    d[parts[-1]] = value


def build_args(key: str, text: str, voice: str = "",
               french: bool = True, instruction: str = "") -> dict:
    """Charge utile complète pour un moteur donné.

    C'est le seul endroit qui sait qu'un moteur veut « prompt » plutôt que
    « text », ou sa voix dans un objet imbriqué. Toute la correction du
    doublage tient dans cette fonction.
    """
    s = spec(key)
    args: dict = {s["text_key"]: text}

    vk = s.get("voice_key") or ""
    if vk:
        v = voice or default_voice_for(key)
        if v:
            _put(args, vk, v)

    if french and s.get("lang_key") and s.get("lang_fr"):
        args[s["lang_key"]] = s["lang_fr"]

    if instruction and key == "seed-speech-v2":
        args["voice_instruction"] = instruction

    return args


def estimate_usd(key: str, n_chars: int) -> float:
    """Coût estimé. Renvoie 0.0 quand le tarif n'a pas été relevé — l'appelant
    doit alors afficher « tarif inconnu », jamais « gratuit »."""
    return round(n_chars / 1000.0 * spec(key).get("price_per_1k", 0.0), 4)
