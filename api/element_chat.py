"""Chat « direction artistique » pour améliorer le prompt d'un élément.

Même esprit que le chat du Studio Images (studio_images/chat.py) : conversation
libre avec Claude + import d'images de référence + synthèse de la discussion en UN
prompt. Ici, spécialisé par TYPE d'élément (Casting, Décor, Accessoire, HMC,
Véhicule) et sortie en FRANÇAIS (comme les optimiseurs de prompt existants —
l'app traduit vers l'anglais au moment de la génération).

Autonome (n'importe pas studio_images) : les quelques aides d'encodage d'images
sont dupliquées ici pour garder l'app principale indépendante du sous-projet.

Signaux : `done` / `failed` / `notice` — JAMAIS `finished` (masquerait le signal
natif QThread.finished → segfault sur le worker suivant).
"""

import base64
import io
import time

from PyQt6.QtCore import QThread, pyqtSignal

from core.config import load_config

_CHAT_MODEL  = "claude-sonnet-5"
_SYNTH_MODEL = "claude-sonnet-5"
# Sonnet 5 active la réflexion adaptative si `thinking` est omis → désactivée ici
# (max_tokens courts) pour ne pas rogner la réponse.
_NO_THINK = {"type": "disabled"}
_KEEP_IMAGE_TURNS = 2   # images pleine résolution : seulement les 2 derniers tours


# ── Brief par type d'élément ──────────────────────────────────────────────────
# (description du sujet, contrainte d'isolation pour la synthèse)
_KIND = {
    "character": (
        "un PORTRAIT de casting (personnage de film) : morphologie, visage, âge, "
        "expression, cheveux, costume, accessoires, attitude.",
        "Cadrage portrait ou plein pied selon l'importance du costume. Fond studio "
        "neutre. Pas de mot « photoréaliste/8K » ; vocabulaire de prise de vue cinéma."),
    "decor": (
        "un DÉCOR / lieu de tournage (intérieur, extérieur, paysage, environnement "
        "urbain) : architecture, matières, mobilier, ambiance, époque, météo, heure.",
        "Plan large d'établissement, vraie lumière et vraie atmosphère (PAS de fond "
        "blanc). Aucune personne dans le cadre."),
    "accessory": (
        "un ACCESSOIRE / prop de film (objet, bijou, arme, pièce de costume) : forme, "
        "matières, couleurs, détails distinctifs.",
        "Objet ISOLÉ sur fond blanc pur, éclairage studio doux, aucune personne, "
        "aucune main, aucune scène."),
    "hmc": (
        "un costume, un maquillage ou une coiffure (HMC) : coupe, matières, couleurs, "
        "style, époque.",
        "Sur mannequin sans visage ou à plat, fond blanc pur, aucune personne "
        "reconnaissable, seulement le vêtement / le maquillage / la coiffure."),
    "vehicle": (
        "un VÉHICULE de film (voiture, moto, camion, bateau, aéronef) : type, époque, "
        "état, couleur, détails.",
        "Véhicule ENTIER isolé sur fond blanc pur, angle 3/4 avant, éclairage studio, "
        "aucune personne, aucune route, aucun décor."),
}


def _brief(kind: str) -> tuple:
    return _KIND.get(kind, _KIND["character"])


def _chat_system(kind: str) -> str:
    subject, _ = _brief(kind)
    return (
        "Tu es directeur artistique et ingénieur de prompt pour la génération d'images "
        "IA en pré-production cinéma (outil PANDORA). Tu aides l'utilisateur à concevoir "
        f"{subject}\n\n"
        "Règles de conversation :\n"
        "- Réponds toujours en FRANÇAIS, de façon concise et concrète.\n"
        "- Tu PEUX recevoir des images de référence jointes : analyse-les réellement "
        "(couleurs, matières, style, composition, ambiance) et appuie tes propositions "
        "dessus. Ne dis jamais que tu ne peux pas voir les images.\n"
        "- Pose 1 à 2 questions de cadrage seulement si vraiment nécessaire, sinon "
        "propose directement une direction (sujet, apparence, matières, lumière/rendu, "
        "palette, ambiance) en 2 à 4 phrases.\n"
        "- Ne rédige PAS le prompt technique final ici sauf si on te le demande — un "
        "bouton « Mettre à jour le prompt » s'en charge. Reste en échange créatif.")


def _synth_system(kind: str) -> str:
    subject, isolation = _brief(kind)
    return (
        "Tu es ingénieur de prompt pour la génération d'images IA (Nano Banana, "
        "Seedream, FLUX, Ideogram, Recraft) en pré-production cinéma.\n\n"
        f"À partir de la conversation fournie, produis UN SEUL prompt image décrivant "
        f"{subject}\n\n"
        "Exigences :\n"
        "- Rédige le prompt en FRANÇAIS (l'application le traduit automatiquement pour "
        "le modèle — l'utilisateur doit pouvoir le lire et le vérifier).\n"
        "- Un seul paragraphe dense et descriptif (max ~120 mots) : sujet et cadrage, "
        "apparence, matières et couleurs, lumière et rendu, style, ambiance.\n"
        f"- {isolation}\n"
        "- N'invente pas d'élément non discuté.\n"
        "- Termes INTERDITS : « photoréaliste », « ultra-détaillé », « 8K », « HDR », "
        "« Unreal Engine », « Octane ». Emploie le vocabulaire de prise de vue cinéma.\n\n"
        "Réponds UNIQUEMENT avec le prompt français. Aucune explication, aucun préfixe, "
        "aucun guillemet englobant l'ensemble.")


# ── Aides d'encodage (dupliquées pour rester indépendant de studio_images) ────

def image_block(path: str, max_px: int = 768) -> dict:
    """Bloc image Anthropic (base64 JPEG redimensionné) depuis un fichier."""
    from PIL import Image
    img = Image.open(path).convert("RGB")
    w, h = img.size
    if max(w, h) > max_px:
        s = max_px / max(w, h)
        img = img.resize((int(w * s), int(h * s)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return {"type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}}


def _to_api_content(content, include_images=True):
    if isinstance(content, str):
        return content
    out = []
    for it in content:
        if it.get("t") == "image":
            if include_images:
                try:
                    out.append(image_block(it["path"]))
                except Exception:
                    pass
            else:
                out.append({"type": "text", "text": "[image envoyée précédemment]"})
        else:
            out.append({"type": "text", "text": it.get("text", "")})
    return out or [{"type": "text", "text": ""}]


def _to_api_messages(history: list) -> list:
    img_turns = [i for i, m in enumerate(history)
                 if m["role"] == "user" and isinstance(m["content"], list)
                 and any(it.get("t") == "image" for it in m["content"])]
    keep = set(img_turns[-_KEEP_IMAGE_TURNS:])
    return [{"role": m["role"],
             "content": _to_api_content(m["content"], include_images=(i in keep))}
            for i, m in enumerate(history)]


def text_of(content) -> str:
    """Partie texte d'un contenu interne (str ou liste d'items)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = [it.get("text", "") for it in content if it.get("t") == "text"]
        imgs = sum(1 for it in content if it.get("t") == "image")
        txt = " ".join(t for t in texts if t)
        if imgs:
            txt = (txt + f"  [{imgs} image(s) jointe(s)]").strip()
        return txt
    return ""


def _friendly_error(e) -> str:
    s = str(e)
    if "rate_limit" in s or "429" in s or "rate limit" in s.lower():
        return ("Limite de débit Claude atteinte (trop de tokens/minute).\n\n"
                "• Attends ~1 minute puis réessaie.\n"
                "• Réduis le nombre d'images jointes à la discussion.")
    return f"Erreur Anthropic : {e}"


def _retry_after(e, default=20) -> int:
    try:
        ra = e.response.headers.get("retry-after")
        if ra:
            return max(1, min(60, int(float(ra))))
    except Exception:
        pass
    return default


# ── Worker : un tour de conversation ──────────────────────────────────────────

class ElementChatWorker(QThread):
    done   = pyqtSignal(str)
    failed = pyqtSignal(str)
    notice = pyqtSignal(str)

    def __init__(self, history: list, kind: str):
        super().__init__()
        self._history = history
        self._kind = kind

    def run(self):
        from core.ai_provider import (ai_name_for_task, chat, humanize_ai_error,
                                      key_error)
        err = key_error(task="element_chat")
        if err:
            self.failed.emit(err)
            return
        messages = _to_api_messages(self._history)
        for attempt in range(3):
            try:
                text = chat(_chat_system(self._kind), messages, tier="creative",
                            max_tokens=700, task="element_chat")
                self.done.emit(text.strip())
                return
            except Exception as e:
                if ("rate_limit" in str(e) or "429" in str(e)) and attempt < 2:
                    wait = _retry_after(e)
                    self.notice.emit(f"Limite de débit — nouvelle tentative dans {wait}s…")
                    time.sleep(wait)
                    continue
                self.failed.emit(humanize_ai_error(
                    f"Erreur {ai_name_for_task('element_chat')} : {e}"))
                return


# ── Worker : synthèse de la conversation en UN prompt ─────────────────────────

class ElementSynthWorker(QThread):
    done   = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, history: list, kind: str):
        super().__init__()
        self._history = history
        self._kind = kind

    def run(self):
        from core.ai_provider import (ai_name_for_task, complete, humanize_ai_error,
                                      key_error)
        err = key_error(task="element_chat")
        if err:
            self.failed.emit(err)
            return
        try:
            convo = "\n\n".join(
                f"{'UTILISATEUR' if m['role'] == 'user' else 'ASSISTANT'} : {text_of(m['content'])}"
                for m in self._history)
            user_msg = (f"Conversation :\n{convo}\n\n"
                        "Produis maintenant le prompt image final en français.")
            for attempt in range(3):
                try:
                    text = complete(_synth_system(self._kind), user_msg,
                                    tier="creative", max_tokens=500,
                                    task="element_chat")
                    self.done.emit(text.strip())
                    return
                except Exception as e:
                    if ("rate_limit" in str(e) or "429" in str(e)) and attempt < 2:
                        time.sleep(_retry_after(e))
                        continue
                    raise
        except Exception as e:
            self.failed.emit(humanize_ai_error(
                f"Erreur {ai_name_for_task('element_chat')} : {e}"))
