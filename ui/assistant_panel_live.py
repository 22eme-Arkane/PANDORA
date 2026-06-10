"""
ui/assistant_panel_live.py — PANDORA | Live : ALIAS SANS DOUBLON.

Ce composant n'a JAMAIS divergé de Cinéma (vérifié : tools/diff_live_cinema.py,
similarité 100 %) — il réexporte donc la classe Cinéma à l'identique au lieu
d'en dupliquer ~871 lignes.

⚠ POUR FAIRE DIVERGER LE LIVE (règle d'or de séparation) :
  1. remplacer CE fichier par une copie complète de ui/assistant_panel.py.py ;
  2. modifier la copie (jamais le fichier Cinéma) ;
  3. déclarer les divergences attendues dans tools/diff_live_cinema.py ;
  4. lancer tools/test_live.py ET tools/test_cinema.py.
"""

from ui.assistant_panel import *          # noqa: F401,F403
from ui.assistant_panel import AssistantPanel, AssistantToggleStrip  # noqa: F401  (exports explicites)
