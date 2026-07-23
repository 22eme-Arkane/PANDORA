"""
api/video_prompt.py — Composition du prompt vidéo Seedance en PROSE anglaise.

Le storyboard travaille en sections françaises ([🎬 ACTION], [🎭 MISE EN SCÈNE]…) —
c'est le format d'ÉDITION (plan par plan, Sound Design, Plan de feu, Moods). Mais
envoyé tel quel à Seedance, ce format balisé et télégraphique donne de mauvais
rendus. Ce module compose, AU MOMENT DE L'ENVOI, un prompt en prose anglaise dense
et fluide — le format qui fonctionne — à partir des sections :

    sujet + décor (fiches casting injectées) → action physique décomposée →
    cadrage/caméra → lumière → ambiance + durée + son → style (en FIN — guide
    officiel Seedance 2.0, corrigé le 2026-07-23).

La composition REMPLACE l'étape de traduction FR→EN (core.lang.translate_to_english)
pour les prompts structurés du storyboard Cinéma : un appel IA au lieu d'un autre,
pas de double traduction. Les différences de FOND corrigées par rapport à l'envoi
brut des sections (diagnostic 2026-07-21, comparaison avec un prompt qui marche) :
  1. l'apparence physique des personnages (fiches casting) est enfin DANS le texte ;
  2. l'action est décrite physiquement (mécanisme du geste), pas télégraphiquement ;
  3. la note interne du Plan de feu (« sources non visibles ») devient de la lumière
     décrite, au lieu de partir comme consigne parasite ;
  4. le son guide l'audio Seedance (generate_audio=True) au lieu d'être strippé ;
  5. la durée est écrite dans le prompt ; 6. le style ouvre le prompt.

Repli : Live (prompts en beats), prompt tapé main, clé manquante ou erreur API →
api/real.py garde le chemin historique (strip + traduction + suffixes). Ce module
ne touche JAMAIS le prompt affiché dans le storyboard.

Appels IA : ai_provider.complete(task="video_prompt") — moteur choisissable dans
Paramètres → Assistant IA → avancés (défaut : Claude Sonnet 5).
"""

from __future__ import annotations


# Nombre minimal de sections « riches » (hors son) pour reconnaître un prompt de
# storyboard Cinéma. Un prompt Live (corps + [🎵 SOUND DESIGN]) ou un texte libre
# n'en a qu'une → il reste sur le chemin historique.
_MIN_RICH_SECTIONS = 3

# Un portrait casting peut être très long : borne par personnage pour garder un
# message de composition compact (le composeur condense de toute façon).
_MAX_NOTE_CHARS = 600

_SYSTEM = """Tu écris des prompts de génération vidéo pour Seedance 2.0 (moteur text-to-video).
On te donne la fiche d'un plan de cinéma (sections en français) et son contexte.
Compose UN prompt en ANGLAIS, en prose dense et fluide, SANS étiquettes, SANS listes,
SANS titres — uniquement des paragraphes courts séparés par une ligne vide.

ORDRE IMPOSÉ (guide officiel Seedance : sujet → action → environnement → caméra →
audio → STYLE EN DERNIER) :
1. SUJET + DÉCOR — qui est à l'image et où : utilise la BIBLE VISUELLE fournie pour
   décrire l'apparence complète de chaque personnage, le décor, les accessoires, HMC
   et véhicules réellement associés au plan ; intègre les positions naturellement.
2. ACTION — décris le geste PHYSIQUEMENT et précisément (quel membre, quel mouvement,
   quel effet visible) ; intègre le contraste dramatique de l'ambiance dans l'action.
3. CADRAGE — valeur de plan, mouvement de caméra, focale, angle, en langage de chef
   opérateur intégré à la prose (une phrase courte).
4. LUMIÈRE — convertis l'intention d'éclairage en description visuelle pure. JAMAIS de
   consigne technique du type « les sources ne sont pas visibles à l'image ».
5. ATMOSPHÈRE + durée en secondes si fournie + courte indication sonore si demandée.
6. STYLE visuel — les mots-clés de style fournis FERMENT le prompt (dernière ligne),
   fusionnés avec toute indication de style de la fiche, sans doublon.

RÈGLES STRICTES :
- Ne TRANSFORME jamais l'action : même geste, même déroulé, même chronologie, même
  intention que la fiche. Tu COMPLÈTES ce qui manque (apparences, précision physique,
  lumière décrite), tu ne réécris pas la scène.
- Les dialogues entre guillemets restent VERBATIM (même langue, mêmes mots, mêmes guillemets).
- N'introduis AUCUN objet, personnage ou événement absent de la fiche — enrichis uniquement
  la précision visuelle et physique de ce qui y figure déjà.
- La BIBLE VISUELLE est canonique : conserve exactement les visages, morphologies,
  âges apparents, costumes, matières, couleurs, accessoires, véhicules et organisation
  spatiale qu'elle décrit. N'invente jamais une variante entre deux plans.
- Le bloc « narrative » de la bible (source_excerpt = extrait exact du scénario,
  rhythm, intention) est ta référence de FIDÉLITÉ : l'action doit rester conforme à
  l'extrait (dialogues compris), le rythme guide le tempo décrit, l'intention guide
  ce que le plan doit faire ressentir. Ne recopie pas ces blocs tels quels.
- Personnages : décris leur APPARENCE (visage, silhouette, costume), jamais leur nom seul.
- Aucun mot de qualité générique (4K, ultra HD, masterpiece, best quality, highly detailed).
- Respecte la contrainte d'éclairage horaire si fournie (mots-clés anglais à conserver).
- AUCUNE limite de longueur : sois aussi détaillé que la fidélité au plan l'exige.
  Ne résume pas, ne tronque pas — chaque personnage et le décor sont toujours
  décrits visuellement, même quand des images de référence accompagnent l'envoi.
- Réponds UNIQUEMENT avec le prompt anglais final, sans commentaire ni préambule."""


def should_compose(prompt: str) -> bool:
    """True si le prompt est un prompt de storyboard Cinéma structuré (assez de
    sections riches pour composer). Un prompt Live (corps + SOUND DESIGN), un texte
    libre ou un plan minimal restent sur le chemin historique."""
    try:
        from core.prompt_sections import is_structured, parse
    except Exception:
        return False
    if not prompt or not is_structured(prompt):
        return False
    s = parse(prompt)
    rich = sum(1 for k in ("action", "staging", "ambiance", "decor", "lighting", "technique")
               if (s.get(k) or "").strip())
    return rich >= _MIN_RICH_SECTIONS


def character_notes_for_shot(shot: dict) -> str:
    """Fiches d'apparence des personnages du plan (« - Nom : description physique »),
    depuis le casting du projet. Chaîne vide si aucun personnage/fiche. Ne lève jamais."""
    try:
        names = [n for n in (shot or {}).get("character_names", []) if n and str(n).strip()]
        if not names:
            return ""
        from core.casting import list_characters
        by_name = {(c.get("name") or "").strip().lower(): c for c in list_characters()}
        lines = []
        for n in names:
            c = by_name.get(str(n).strip().lower())
            if not c:
                continue
            try:
                from core.visual_identity import canonical_description
                bits = canonical_description(c)
            except Exception:
                bits = " ".join(x.strip() for x in (
                    c.get("description", ""), c.get("prompt", "")
                ) if x and x.strip())
            if bits:
                lines.append(f"- {c.get('name')} : {bits[:_MAX_NOTE_CHARS]}")
        return "\n".join(lines)
    except Exception:
        return ""


def visual_context_for_shot(shot: dict) -> str:
    """Bible canonique complète du plan : style + toutes les familles d'entités."""
    try:
        from core.visual_context import format_visual_context
        return format_visual_context(shot or {})
    except Exception:
        return ""


def _build_user_message(prompt: str, style_suffix: str, time_suffix: str,
                        duration, character_notes: str, include_sound: bool,
                        sound_notes: str = "", visual_context: str = "") -> str:
    """Message utilisateur du composeur — fiche du plan + contexte. Le son passe
    TOUJOURS par le bloc dédié [AMBIANCE SONORE] : `sound_notes` (capturé par
    tab_t2v AVANT son strip historique) ou, à défaut, la section [🎵 SOUND DESIGN]
    encore présente dans le prompt — jamais les deux (la section est retirée)."""
    try:
        from core.prompt_sections import strip_for_video, sound_of
        sound_notes = (sound_notes or "").strip() or sound_of(prompt).strip()
        prompt = strip_for_video(prompt) or prompt
    except Exception:
        sound_notes = (sound_notes or "").strip()
    parts = [f"[SECTIONS DU PLAN]\n{prompt.strip()}"]
    parts.append("[FICHES PERSONNAGES]\n"
                 + (character_notes.strip() if character_notes.strip() else "(aucune)"))
    parts.append("[BIBLE VISUELLE CANONIQUE DU PLAN — source de vérité]\n"
                 + (visual_context.strip() if visual_context.strip() else "(indisponible)"))
    parts.append("[STYLE VIDÉO — mots-clés anglais, à placer EN FIN (dernière ligne)]\n"
                 + (style_suffix.strip() if style_suffix.strip() else "(aucun)"))
    if time_suffix.strip():
        parts.append(f"[CONTRAINTE D'ÉCLAIRAGE HORAIRE — anglais, à respecter]\n{time_suffix.strip()}")
    if duration:
        parts.append(f"[DURÉE] {duration} seconds")
    if include_sound and sound_notes:
        parts.append(f"[AMBIANCE SONORE — à évoquer brièvement en fin de prompt]\n{sound_notes}")
    parts.append("[SON] " + ("inclure une courte indication sonore en fin de prompt"
                             if include_sound else "NE PAS mentionner le son"))
    return "\n\n".join(parts)


def compose(prompt: str, style_suffix: str = "", time_suffix: str = "",
            duration=None, character_notes: str = "", include_sound: bool = True,
            sound_notes: str = "", visual_context: str = "") -> str:
    """Compose la prose anglaise du plan. Renvoie "" en cas d'échec (l'appelant
    replie alors sur le chemin historique strip + traduction). Appel RÉSEAU —
    à exécuter dans un QThread (GenerationWorker), jamais sur le thread UI."""
    try:
        from core import ai_provider
        user = _build_user_message(prompt, style_suffix or "", time_suffix or "",
                                   duration, character_notes or "", include_sound,
                                   sound_notes or "", visual_context or "")
        # 8192 tokens : plus aucune limite de longueur sur la prose (décision
        # Matthieu 2026-07-23 — les troncatures coûtent plus cher que les tokens).
        out = (ai_provider.complete(_SYSTEM, user, tier="creative",
                                    max_tokens=8192, task="video_prompt") or "").strip()
        if not validate_composed_prompt(out, prompt)["valid"]:
            return ""
        return out
    except Exception:
        return ""


def validate_composed_prompt(output: str, source_prompt: str = "") -> dict:
    """Validation déterministe minimale avant envoi au moteur vidéo."""
    import re
    errors, warnings = [], []
    text = (output or "").strip()
    low = text.lower()
    if not text:
        errors.append("réponse vide")
    if low.startswith(("voici", "here is", "here's")):
        errors.append("préambule parasite")
    if re.search(r"^\s*\[[^\]]+\]", text, flags=re.MULTILINE):
        errors.append("sections internes encore présentes")
    # Plus AUCUNE borne de longueur (décision Matthieu 2026-07-23) : ni plafond
    # (l'ancien « > 2200 » rejetait des proses valides), ni plancher. Seul un
    # avertissement informatif subsiste pour une prose anormalement courte.
    if text and len(text) < 200:
        warnings.append("prompt très court")
    banned = ("masterpiece", "best quality", "ultra hd", "4k")
    if any(word in low for word in banned):
        errors.append("mots de qualité génériques")
    # Les dialogues explicites doivent rester verbatim jusqu'à l'étape dédiée de
    # traduction des dialogues dans api.real.
    quoted = []
    for pattern in (r'"([^"\n]{1,300})"', r'«([^»\n]{1,300})»', r'“([^”\n]{1,300})”'):
        quoted.extend(re.findall(pattern, source_prompt or ""))
    for dialogue in quoted:
        if dialogue not in text:
            errors.append(f"dialogue omis ou modifié : {dialogue[:60]}")
    return {"valid": not errors, "errors": errors, "warnings": warnings}
