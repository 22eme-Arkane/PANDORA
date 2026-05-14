"""
Traduit tous les seedance_prompt anglais du storyboard en français.
À exécuter une seule fois depuis le dossier VS Code.

Usage:
    python tools/translate_storyboard_prompts.py
"""

import json
import os
import sys
import time

# Ajoute le répertoire parent au path pour importer core/
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.config import load_config

STORYBOARD_JSON = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data", "storyboard", "index.json"
)

_SYSTEM = (
    "Tu es un traducteur spécialisé dans les prompts de génération vidéo IA. "
    "Traduis le texte anglais fourni en français, en conservant tous les détails techniques, "
    "les termes cinématographiques, les noms propres et la structure du prompt exactement. "
    "Retourne UNIQUEMENT le texte traduit. Aucune explication, aucun préfixe, aucune guillemet."
)


def translate_to_french(text: str, client) -> str:
    """Traduit un prompt anglais vers le français via Claude Haiku."""
    if not text or not text.strip():
        return text
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=600,
            system=_SYSTEM,
            messages=[{"role": "user", "content": text}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        print(f"  WARN traduction: {e}")
        return text


def main():
    cfg = load_config()
    key = cfg.get("anthropic_key", "").strip()
    if not key:
        print("ERREUR: Cle Anthropic manquante dans config.json (anthropic_key)")
        sys.exit(1)

    import anthropic
    client = anthropic.Anthropic(api_key=key)

    if not os.path.exists(STORYBOARD_JSON):
        print(f"ERREUR: Fichier non trouve : {STORYBOARD_JSON}")
        sys.exit(1)

    with open(STORYBOARD_JSON, "r", encoding="utf-8") as f:
        shots = json.load(f)

    total = len(shots)
    translated = 0
    skipped = 0

    print(f"{total} plans trouves")
    print("-" * 60)

    for i, shot in enumerate(shots):
        prompt = shot.get("seedance_prompt", "").strip()
        num = shot.get("number", i + 1)
        title = shot.get("scene_title", "")

        if not prompt:
            skipped += 1
            continue

        # Heuristique simple : si le prompt contient des mots anglais courants, on traduit
        en_markers = (" the ", " a ", " an ", " is ", " are ", " shot ", " with ", " from ", " and ", " into ")
        needs_translation = any(m in f" {prompt.lower()} " for m in en_markers)

        if not needs_translation:
            print(f"  [{i+1}/{total}] Plan {num} - deja en francais, ignore")
            skipped += 1
            continue

        print(f"  [{i+1}/{total}] Plan {num} - {title[:40]}...", end="", flush=True)
        fr = translate_to_french(prompt, client)
        shots[i]["seedance_prompt"] = fr
        translated += 1
        print(" OK")

        # Petite pause pour éviter rate-limit
        if translated % 10 == 0:
            time.sleep(0.5)

    # Sauvegarde
    with open(STORYBOARD_JSON, "w", encoding="utf-8") as f:
        json.dump(shots, f, ensure_ascii=False, indent=2)

    print("-" * 60)
    print(f"{translated} prompts traduits, {skipped} ignores -> {STORYBOARD_JSON}")


if __name__ == "__main__":
    main()
