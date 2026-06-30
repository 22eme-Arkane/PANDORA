"""
Workers Claude — dialogue créatif et synthèse de prompt image.

ChatWorker        : conversation libre avec Claude (directeur artistique YouTube).
SynthPromptWorker : condense la discussion en UN prompt image anglais optimisé.
"""

import base64
import io
import time

from PyQt6.QtCore import QThread, pyqtSignal

_CHAT_MODEL  = "claude-sonnet-5"
_SYNTH_MODEL = "claude-sonnet-5"
# Sonnet 5 active la réflexion adaptative si `thinking` est omis → désactivée ici
# (max_tokens courts : 500-700) pour ne pas rogner la réponse.
_NO_THINK = {"type": "disabled"}

# Nombre de tours utilisateur récents pour lesquels on renvoie les images en pleine
# résolution. Au-delà, les images deviennent un simple marqueur texte (économie de
# tokens — évite de dépasser la limite de débit Anthropic).
_KEEP_IMAGE_TURNS = 2


# ── Historique : schéma interne (chemins, pas de base64) ─────────────────────
# Un message = {"role": "user"|"assistant", "content": <str> | [items]}
# item = {"t": "text", "text": str}  |  {"t": "image", "path": str}
# Ce schéma se sérialise en JSON (projets) ET se ré-encode pour l'API à l'envoi.

def image_block(path: str, max_px: int = 768) -> dict:
    """Construit un bloc image Anthropic (base64 JPEG, redimensionné) depuis un fichier."""
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


def to_api_content(content, include_images=True):
    """Convertit un contenu interne vers le format Anthropic.

    include_images=False → les images sont remplacées par un marqueur texte
    (utilisé pour les anciens tours, afin d'économiser des tokens)."""
    if isinstance(content, str):
        return content
    out = []
    for it in content:
        if it.get("t") == "image":
            if include_images:
                try:
                    out.append(image_block(it["path"]))
                except Exception:
                    pass  # image introuvable → ignorée
            else:
                out.append({"type": "text", "text": "[image envoyée précédemment]"})
        else:
            out.append({"type": "text", "text": it.get("text", "")})
    return out or [{"type": "text", "text": ""}]


def to_api_messages(history: list) -> list:
    """Construit les messages API. Pour limiter les tokens d'entrée, seules les
    images des _KEEP_IMAGE_TURNS derniers tours utilisateur sont envoyées en entier ;
    les plus anciennes deviennent un marqueur texte."""
    img_turns = [i for i, m in enumerate(history)
                 if m["role"] == "user" and isinstance(m["content"], list)
                 and any(it.get("t") == "image" for it in m["content"])]
    keep = set(img_turns[-_KEEP_IMAGE_TURNS:])
    return [{"role": m["role"],
             "content": to_api_content(m["content"], include_images=(i in keep))}
            for i, m in enumerate(history)]


def friendly_error(e) -> str:
    """Message d'erreur lisible — cas particulier de la limite de débit (429)."""
    s = str(e)
    if "rate_limit" in s or "429" in s or "rate limit" in s.lower():
        return ("Limite de débit Claude atteinte (trop de tokens/minute sur ton palier).\n\n"
                "• Attends ~1 minute puis réessaie.\n"
                "• Réduis le nombre d'images jointes à la discussion.\n"
                "• Recharge ton crédit Anthropic pour passer à un palier supérieur "
                "(⚙ Clés API → 💳 Recharger).")
    return f"Erreur Anthropic : {e}"


def _retry_after(e, default=20) -> int:
    """Lit l'en-tête retry-after de l'erreur si présent, sinon `default` (secondes)."""
    try:
        ra = e.response.headers.get("retry-after")
        if ra:
            return max(1, min(60, int(float(ra))))
    except Exception:
        pass
    return default


def text_of(content) -> str:
    """Extrait la partie texte d'un contenu interne (str ou liste d'items)."""
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

# ── Brief du directeur artistique ─────────────────────────────────────────────
_CHAT_SYSTEM = """\
Tu es un directeur artistique polyvalent et ingénieur de prompt pour la génération \
d'images IA. Tu aides l'utilisateur — créateur de PANDORA (outil de pré-production \
cinéma + IA) — à concevoir TOUT type de visuel : logos et identités de marque, \
vignettes et bannières YouTube, affiches, illustrations, key arts, visuels réseaux \
sociaux, icônes, etc.

Règles de conversation :
- Réponds toujours en FRANÇAIS, de façon concise et concrète.
- Tu PEUX recevoir des images de référence jointes par l'utilisateur : analyse-les \
réellement (couleurs, composition, style, logo, typo, ambiance) et appuie tes \
propositions dessus. Ne dis jamais que tu ne peux pas voir les images.
- Pose 1 à 2 questions de cadrage seulement si vraiment nécessaire (sujet, usage, \
émotion, texte à afficher, ambiance, couleurs/branding). Sinon, propose directement.
- Adapte ton expertise au type de visuel :
  · Logo / branding → formes simples et mémorisables, lisibilité à petite taille, \
palette restreinte, fond propre, déclinable. Un logo pictural/vectoriel évite le photo-réalisme.
  · Vignette YouTube → point focal clair, visage expressif si pertinent, contraste fort, \
titre court et ÉNORME lisible même en miniature, couleurs qui claquent, profondeur.
  · Bannière → composition large, zone centrale sûre (« safe area »), branding cohérent.
  · Affiche / key art → hiérarchie visuelle, ambiance cinématographique, espace pour le titre.
- Quand tu proposes une direction, décris-la en 2-4 phrases : sujet, composition, \
lumière/rendu, palette, emplacement et contenu du texte s'il y en a.
- Ne génère PAS le prompt technique final ici sauf si on te le demande — un autre bouton \
s'en charge. Reste en mode échange créatif.\
"""

_SYNTH_SYSTEM = """\
Tu es ingénieur de prompt pour la génération d'images IA (Nano Banana, Ideogram, FLUX, Recraft).

À partir de la conversation fournie, produis UN SEUL prompt image, en ANGLAIS, prêt à l'emploi.

Exigences du prompt de sortie :
- Anglais, dense et descriptif, en un paragraphe (max ~150 mots).
- Décris : sujet et cadrage, composition, lumière/rendu, palette de couleurs, ambiance, style.
- Adapte au format cible indiqué (logo, vignette, bannière, affiche, etc.) :
  · Logo → mention explicite « logo », style propre (flat / vector / minimal selon le brief), \
formes simples, fond uni ou transparent, lisible en petit, pas de scène complexe.
  · Vignette/bannière → fort contraste, point focal net, profondeur, accroche immédiate.
- Si du texte doit apparaître, écris-le EXACTEMENT entre guillemets droits, ex. : \
the text "MON TITRE" in bold, en précisant placement, taille et couleur. Texte gros et lisible.
- N'invente pas de filigrane ni d'élément non demandé.

Réponds UNIQUEMENT avec le prompt anglais. Aucune explication, aucun préfixe, aucun guillemet \
englobant l'ensemble.\
"""


class ChatWorker(QThread):
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)
    notice   = pyqtSignal(str)   # message d'attente (ex. nouvelle tentative)

    def __init__(self, api_key: str, history: list):
        super().__init__()
        self._key = api_key
        # history : list[{"role": "user"|"assistant", "content": str|list}]
        self._history = history

    def run(self):
        if not self._key:
            self.failed.emit("Clé API Anthropic manquante.\nRenseigne-la dans ⚙ Clés API.")
            return
        import anthropic
        client = anthropic.Anthropic(api_key=self._key)
        messages = to_api_messages(self._history)
        for attempt in range(3):
            try:
                msg = client.messages.create(
                    model=_CHAT_MODEL,
                    max_tokens=700,
                    thinking=_NO_THINK,
                    system=_CHAT_SYSTEM,
                    messages=messages,
                )
                self.finished.emit(msg.content[0].text.strip())
                return
            except Exception as e:
                is_rate = "rate_limit" in str(e) or "429" in str(e)
                if is_rate and attempt < 2:
                    wait = _retry_after(e)
                    self.notice.emit(f"Limite de débit atteinte — nouvelle tentative dans {wait}s…")
                    time.sleep(wait)
                    continue
                self.failed.emit(friendly_error(e))
                return


class SynthPromptWorker(QThread):
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, api_key: str, history: list, format_label: str):
        super().__init__()
        self._key = api_key
        self._history = history
        self._format = format_label

    def run(self):
        if not self._key:
            self.failed.emit("Clé API Anthropic manquante.\nRenseigne-la dans ⚙ Clés API.")
            return
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self._key)

            convo = "\n\n".join(
                f"{'UTILISATEUR' if m['role'] == 'user' else 'CLAUDE'} : {text_of(m['content'])}"
                for m in self._history
            )
            user_msg = (
                f"Format cible : {self._format}.\n\n"
                f"Conversation :\n{convo}\n\n"
                "Produis maintenant le prompt image anglais final."
            )
            for attempt in range(3):
                try:
                    msg = client.messages.create(
                        model=_SYNTH_MODEL,
                        max_tokens=500,
                        thinking=_NO_THINK,
                        system=_SYNTH_SYSTEM,
                        messages=[{"role": "user", "content": user_msg}],
                    )
                    self.finished.emit(msg.content[0].text.strip())
                    return
                except Exception as e:
                    if ("rate_limit" in str(e) or "429" in str(e)) and attempt < 2:
                        time.sleep(_retry_after(e))
                        continue
                    raise
        except Exception as e:
            self.failed.emit(friendly_error(e))
