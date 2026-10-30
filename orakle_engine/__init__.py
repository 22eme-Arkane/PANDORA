"""Moteur de dictée d'ORAKLE, embarqué dans PANDORA (27/10/2026).

Copie À L'IDENTIQUE de deux modules d'ORAKLE (même auteur, GPL-3.0, voir LICENSE
et NOTICE) : `recorder` (micro) et `transcriber` (Whisper local). Ne pas les
modifier ici : les corriger dans ORAKLE puis lancer tools/update_orakle_engine.py.
Tout ce qui est propre à PANDORA vit dans core/dictation.py et ui/dictation.py.
"""

#: Version d'ORAKLE dont viennent les modules (mise à jour par le script).
VERSION = "0.1.3"
