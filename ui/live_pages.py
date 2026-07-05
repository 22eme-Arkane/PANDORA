"""
ui/live_pages.py — Point d'import central des composants PANDORA | Live.

Chaque composant Live est une COPIE COMPLÈTE et INDÉPENDANTE de son équivalent
Cinéma (fichiers ui/*_live.py). Modifier le Live ne touche JAMAIS Cinéma, et
inversement — on peut travailler librement et séparément sur les deux modules.

Correspondances :
  Cinéma                     →  Copie Live (indépendante)
  ui/page_projects.py        →  ui/page_projects_live.py
  ui/page_scenario.py        →  ui/page_scenario_live.py     (Conducteur)
  ui/page_storyboard.py      →  ui/page_storyboard_live.py   (Séquences Live/Mapping)
  ui/page_castings.py        →  ui/page_castings_live.py
  ui/page_accessories.py     →  ui/page_accessories_live.py
  ui/page_vehicles.py        →  ui/page_vehicles_live.py
  ui/tab_video_engines.py    →  ui/tab_video_engines_live.py (Génération directe + outils VJ/Mapping)
  ui/tab_history.py          →  ui/tab_history_live.py
  ui/assistant_panel.py      →  ui/assistant_panel_live.py
  ui/dialog_user_manual.py   →  ui/dialog_user_manual_live.py
  ui/dialog_contact.py       →  ui/dialog_contact_live.py

Déjà dédiés Live (pas de copie nécessaire) : page_live_settings, tab_video_library_live,
tab_modify_live, live_studio_widget.
"""

import core.storyboard as _sb

from ui.page_projects_live      import PageProjects     as ProjetsLivePage
from ui.page_scenario_live      import PageScenario     as ConducteurPage
from ui.page_castings_live      import PageCastings     as CastingLivePage
from ui.page_accessories_live   import PageAccessories  as AccessoiresLivePage
from ui.page_vehicles_live      import PageVehicles     as VehiculesLivePage
from ui.tab_video_engines_live  import TabVideoEngines  as TabVideoEnginesLive
from ui.tab_history_live        import TabHistory       as TabHistoryLive
from ui.assistant_panel_live    import AssistantPanel   as AssistantPanelLive
from ui.dialog_user_manual_live import UserManualDialog as UserManualDialogLive
from ui.dialog_contact_live     import ContactDialog    as ContactDialogLive
from ui.page_storyboard_live    import PageStoryboard   as _PageStoryboardLive


# Les deux séquences partagent la copie Storyboard Live, avec un namespace de
# données distinct (live_seq_live / live_seq_mapping) — seul ajout propre au Live.

# Ordre conducteur par défaut — validé par Matthieu (capture 2026-06-10) :
# grip · Mood · Acte · Plan · TC · Prompt vidéo/son · Musique · BPM · Vitesse ·
# Durée · Notes/Repère · Transition · Acteurs · Accessoires ·
# (colonnes caméra/décor, masquées selon la page) · boutons.
# Drag toujours possible ensuite (l'ordre personnalisé du projet prime).
# « Référence » (logique 22) affichée juste après « Mood » (logique 1), comme au Cinéma.
_LIVE_DEFAULT_ORDER = [0, 1, 22, 2, 3, 16, 4, 17, 18, 10, 15, 20, 19, 14, 13,
                       5, 6, 7, 8, 9, 11, 12, 21]


class SequenceLivePage(_PageStoryboardLive):
    """Séquences Live — Storyboard Live (namespace de données dédié).

    Héritage Cinéma retiré : Mouvement (6), Décor (11), Heure (12) —
    les décors n'existent pas dans le Live et le mouvement vient du prompt."""
    _live_ns = "live_seq_live"
    _hidden_cols = {6, 11, 12}
    _default_col_order = _LIVE_DEFAULT_ORDER

    def __init__(self):
        _sb.set_namespace(self._live_ns)
        super().__init__()


class SequenceMappingPage(_PageStoryboardLive):
    """Séquences Mapping — Storyboard Live (namespace de données dédié).

    En mapping (façade fixe, caméra fixe, image de référence du bâtiment), on masque
    les colonnes inutiles : Axe Caméra (5), Mouvement (6), Valeur (7), Focal (8),
    Distance (9), Décor (11), Heure (12)."""
    _live_ns = "live_seq_mapping"
    _hidden_cols = {5, 6, 7, 8, 9, 11, 12}
    _default_col_order = _LIVE_DEFAULT_ORDER

    def __init__(self):
        _sb.set_namespace(self._live_ns)
        super().__init__()
