"""
Worker fal.ai — génération d'image multi-moteurs (voir engines.py).

Sans clé fal.ai : mode mock (placeholder Pillow) pour tester l'UI sans coût.
Avec clé : appel réel fal_client.subscribe vers le moteur sélectionné.

Réutilise le pattern de api/nano_banana.py (extraction d'URL, encodage base64
des références).
"""

import base64
import mimetypes
import os
import time

from PyQt6.QtCore import QThread, pyqtSignal

import engines


def _extract_image_url(result) -> str:
    """Extrait l'URL de la première image d'une réponse fal.ai."""
    if not isinstance(result, dict):
        raise RuntimeError(f"Réponse API inattendue : {str(result)[:200]}")
    images = result.get("images")
    if not images:
        # certains moteurs renvoient {"image": {...}}
        single = result.get("image")
        if isinstance(single, dict) and single.get("url"):
            return single["url"]
        raise RuntimeError(f"Aucune image dans la réponse API : {str(result)[:200]}")
    url = images[0].get("url", "") if isinstance(images[0], dict) else ""
    if not url:
        raise RuntimeError("URL d'image manquante dans la réponse API.")
    return url


def _data_url(path: str) -> str:
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"


def _export_resized(src_path: str, out_path: str, target: tuple) -> str:
    """Recadre/redimensionne (cover) l'image aux dimensions exactes demandées."""
    try:
        from PIL import Image
        tw, th = target
        img = Image.open(src_path).convert("RGB")
        w, h = img.size
        scale = max(tw / w, th / h)
        nw, nh = int(round(w * scale)), int(round(h * scale))
        img = img.resize((nw, nh), Image.LANCZOS)
        left = (nw - tw) // 2
        top = (nh - th) // 2
        img = img.crop((left, top, left + tw, top + th))
        img.save(out_path, "PNG")
        return out_path
    except Exception:
        return src_path


class ImageWorker(QThread):
    progress = pyqtSignal(int, str)
    # « done » et JAMAIS « finished » : un signal nommé finished masque le signal
    # natif QThread.finished (état Qt incohérent → segfault sur le worker suivant).
    done     = pyqtSignal(list)   # liste des fichiers générés (PNG taille exacte, ou SVG)
    failed   = pyqtSignal(str)

    def __init__(self, fal_key, engine_key, prompt, resolution,
                 ref_paths, out_dir, target_size, count=1, engine_keys=None):
        super().__init__()
        self._key     = (fal_key or "").strip()
        self._engine  = engine_key
        self._prompt  = prompt
        self._res     = resolution
        self._refs    = [p for p in (ref_paths or []) if p and os.path.isfile(p)][:14]
        self._out_dir = out_dir
        self._target  = target_size
        # FILE D'ATTENTE : une entrée = une image, générée avec CE moteur.
        #   engine_keys → balayage « tous les moteurs » (un moteur par entrée) ;
        #   sinon        → lot classique de `count` images sur le moteur choisi.
        self._jobs    = ([k for k in engine_keys if k] if engine_keys
                         else [engine_key] * max(1, int(count)))
        self._count   = len(self._jobs)

    def run(self):
        os.makedirs(self._out_dir, exist_ok=True)
        if not self._key:
            self._mock()
        else:
            self._real()

    # ── Mock ──────────────────────────────────────────────────────────────────
    def _mock(self):
        self.progress.emit(20, "Mode mock (pas de clé fal.ai)…")
        paths = []
        try:
            from PIL import Image, ImageDraw
            n = len(self._jobs)
            for i, ekey in enumerate(self._jobs):
                if self.isInterruptionRequested():
                    break
                name = engines.short_label(ekey)
                self.progress.emit(20 + int((i + 1) / n * 70),
                                   f"[{i + 1}/{n}] {name} — placeholder…")
                time.sleep(0.2)
                tw, th = self._target
                img = Image.new("RGB", (tw, th), (24, 27, 44))
                d = ImageDraw.Draw(img)
                d.rectangle([8, 8, tw - 8, th - 8], outline=(78, 205, 196), width=4)
                d.text((40, 40), f"MOCK {i + 1}/{n} · {name}", fill=(78, 205, 196))
                d.text((40, 70), (self._prompt or "(prompt vide)")[:240], fill=(230, 236, 245))
                # Nom du moteur EN FIN de nom de fichier
                p = os.path.join(
                    self._out_dir,
                    f"studio_{int(time.time())}_{i}_mock_{engines.slug_for(ekey)}.png")
                img.save(p, "PNG")
                paths.append(p)
        except Exception as e:
            self.failed.emit(f"Pillow indisponible pour le mock : {e}")
            return
        self.progress.emit(100, f"{len(paths)} placeholder(s) (mock).")
        self.done.emit(paths)

    # ── Réel ──────────────────────────────────────────────────────────────────
    def _real(self):
        paths, errors = [], []
        try:
            import fal_client
            import requests

            os.environ["FAL_KEY"] = self._key

            ref_urls = []
            if self._refs:
                self.progress.emit(6, "Encodage des images de référence…")
                ref_urls = [_data_url(p) for p in self._refs]
        except Exception as e:
            self.failed.emit(f"Erreur fal.ai : {e}")
            return

        n = len(self._jobs)
        for i, ekey in enumerate(self._jobs):
            # « Annuler » interrompt la FILE : les images restantes ne sont pas
            # demandées — donc pas facturées. Sans ce test, annuler un lot de 10
            # laissait partir les 10 appels payants.
            if self.isInterruptionRequested():
                break
            name = engines.short_label(ekey)
            base = 8 + int(i / n * 84)
            self.progress.emit(base, f"[{i + 1}/{n}] {name} — envoi à fal.ai…")
            try:
                endpoint, args, out_kind = engines.build_request(
                    ekey, self._prompt, self._target, self._res, ref_urls)
                result = fal_client.subscribe(endpoint, arguments=args)

                self.progress.emit(base + int(84 / n * 0.6),
                                   f"[{i + 1}/{n}] {name} — téléchargement…")
                url = _extract_image_url(result)
                data = requests.get(url, timeout=180).content

                ts   = int(time.time())
                slug = engines.slug_for(ekey)   # nom du moteur EN FIN de fichier
                if out_kind == "svg":
                    final = os.path.join(self._out_dir, f"studio_{ts}_{i}_{slug}.svg")
                    with open(final, "wb") as f:
                        f.write(data)
                else:
                    raw = os.path.join(self._out_dir, f"studio_{ts}_{i}_raw_{slug}.png")
                    with open(raw, "wb") as f:
                        f.write(data)
                    final = os.path.join(self._out_dir, f"studio_{ts}_{i}_{slug}.png")
                    final = _export_resized(raw, final, self._target)
                paths.append(final)
            except Exception as e:
                # Un moteur en échec ne doit PAS annuler la file : sur un balayage,
                # les autres moteurs doivent aboutir malgré un endpoint capricieux.
                errors.append(f"{name} : {e}")
                self.progress.emit(base, f"[{i + 1}/{n}] {name} — échec, on continue…")
                continue

        if not paths:
            detail = ("\n\n" + "\n".join(errors)) if errors else ""
            self.failed.emit("Aucune image générée." + detail)
            return
        if errors:
            recale = ", ".join(e.split(" : ")[0] for e in errors)
            self.progress.emit(100, f"{len(paths)} image(s) · en échec : {recale}")
        else:
            self.progress.emit(100, f"{len(paths)} image(s) générée(s) !")
        self.done.emit(paths)
