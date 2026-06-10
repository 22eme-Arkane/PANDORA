"""
tools/test_cinema.py — Harnais de non-régression PANDORA | Cinéma.

La protection n°1 du pont Cinéma↔Live : il FIGE le comportement Cinéma.
À lancer avant chaque build et après toute session de modifications Live :

    C:\\Users\\22eme\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe tools\\test_cinema.py

- Headless (Qt offscreen), données en dossier temporaire, AUCUN appel réseau.
- Si un test casse après une session Live → une modification a fui vers Cinéma.

Code de sortie : 0 si tout passe, 1 sinon.
"""

import os
import sys
import tempfile
import traceback
import inspect

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

APP = QApplication([])
QDialog.exec = lambda self: 0
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

import core.context as ctx
_TMP = tempfile.mkdtemp(prefix="pandora_cinema_test_")
ctx.set_project_path(_TMP)
ctx.set_project_id("test_cinema")

_TESTS = []


def test(fn):
    _TESTS.append(fn)
    return fn


# ══════════════════════════════════════════════════════════════════════════════
# Moteurs IA — le port Live → Cinéma est complet et le reste
# ══════════════════════════════════════════════════════════════════════════════

@test
def selecteur_ia_present():
    """Paramètres Cinéma : sélecteur d'assistant IA (Claude/Fable 5/Mistral/Ollama)."""
    from ui.page_settings import SettingsPage
    p = SettingsPage()
    assert p.ai_combo.count() == 4, "4 choix d'assistant"
    labels = [p.ai_combo.itemText(i) for i in range(4)]
    assert any("Fable 5" in x for x in labels), "Fable 5 proposé"
    assert any("Mistral" in x for x in labels) and any("Ollama" in x for x in labels)
    p.ai_combo.setCurrentIndex(2)
    assert not p.mistral_input.isHidden(), "champ Mistral conditionnel"
    # La sauvegarde écrit bien les clés de config IA
    src = inspect.getsource(SettingsPage.save)
    for key in ("ai_provider", "ai_model_creative", "mistral_key", "ollama_url"):
        assert key in src, f"save() persiste {key}"


@test
def workers_cinema_routes_via_provider():
    """api/screenplay.py : tout le TEXTE passe par core.ai_provider (VISION = 2 sites)."""
    import api.screenplay as s
    src = inspect.getsource(s)
    assert "core.ai_provider" in src, "screenplay routé via la couche IA"
    assert src.count("anthropic.Anthropic(") == 2, "seuls les 2 sites VISION restent directs"
    for mod_name in ("api.enhance", "api.assistant", "core.lang"):
        mod = __import__(mod_name, fromlist=["_"])
        assert "anthropic.Anthropic(" not in inspect.getsource(mod), \
            f"{mod_name} : appel anthropic direct interdit"


@test
def branding_libelles_partage():
    """translate() rebaptise « Claude » selon l'assistant actif — partagé Cinéma/Live."""
    import core.ai_provider as ap
    from core.i18n import translate
    ap._NAME_CACHE = "Fable 5"
    try:
        assert "Fable 5" in translate("☁  Claude IA")
    finally:
        ap.refresh_name_cache()
    # Les boutons IA de la page Scénario passent par translate()
    src = inspect.getsource(__import__("ui.page_scenario", fromlist=["_"]))
    assert "QLabel(translate(label))" in src, "boutons IA Scénario routés par translate"


# ══════════════════════════════════════════════════════════════════════════════
# Prompts Cinéma — enrichis mais FIDÈLES au scénario
# ══════════════════════════════════════════════════════════════════════════════

@test
def prompts_storyboard_cinema():
    import api.screenplay as s
    t = s._GENERATE_STORYBOARD_TMPL
    assert "DETAILED, dense video generation prompt" in t, "prompt vidéo détaillé"
    assert "WITHOUT inventing any new story element" in t, "fidélité au scénario"
    assert "duration" in t and "15.0" in t, "contrainte durée Seedance"


@test
def prompts_mise_en_page_cinema():
    import api.screenplay as s
    assert "TRÈS DÉTAILLÉ" in s._FORMAT_PANDORA and "FIDÈLE au scénario" in s._FORMAT_PANDORA
    assert "HIGHLY DETAILED" in s._FORMAT_PANDORA_EN and "FAITHFUL" in s._FORMAT_PANDORA_EN
    # Le vocabulaire scénario (INT./EXT.) reste LÉGITIME côté Cinéma
    assert "INT./EXT." in s._FORMAT_PANDORA, "en-têtes de scène Cinéma préservés"


# ══════════════════════════════════════════════════════════════════════════════
# Stabilité / séparation
# ══════════════════════════════════════════════════════════════════════════════

@test
def anticrash_preview_translate():
    """Le fix QThread/abandon_thread est bien reporté côté Cinéma."""
    from ui.tab_t2v import TabT2V
    src = inspect.getsource(TabT2V._start_preview_translate)
    assert "abandon_thread" in src, "anti-crash reporté (quit() inopérant sur run())"


@test
def separation_live_intacte():
    """Aucune fonctionnalité Live n'a fui dans les fichiers Cinéma."""
    import ui.dialog_shot as shot_c
    assert "sound_prompt" not in inspect.getsource(shot_c), "pas de prompt son côté Cinéma"
    import ui.page_storyboard as sb_c
    src = inspect.getsource(sb_c)
    assert "_HIDDEN_COLS" not in src, "pas de masquage de colonnes côté Cinéma"
    assert "music_track" not in src, "pas de colonne Musique côté Cinéma"
    import ui.tab_t2v as t2v_c
    src = inspect.getsource(t2v_c)
    assert "_seq_mode" not in src, "pas de sélecteur Live/Mapping côté Cinéma"
    assert "live_building" not in src, "pas de façade côté Cinéma"
    assert "from davinci.bridge import resolve" in src, "DaVinci préservé côté Cinéma"


@test
def namespace_storyboard_reset():
    """PandoraWindow remet le namespace storyboard (anti-contamination Live)."""
    import ui.pandora_window as w
    src = inspect.getsource(w)
    assert 'set_namespace("storyboard")' in src, "reset namespace au lancement Cinéma"


@test
def construction_pages_cinema():
    """Les pages Cinéma clés se construisent sans erreur (smoke test)."""
    import core.storyboard as sb
    sb.set_namespace("storyboard")
    from ui.page_scenario import PageScenario
    from ui.page_storyboard import PageStoryboard
    from ui.dialog_shot import ShotDialog
    PageScenario()
    PageStoryboard()
    d = ShotDialog(shot={"id": "s1", "number": 1, "seedance_prompt": "x"})
    assert d._seedance_prompt.toPlainText() == "x"


@test
def prompt_mood_cinema_inchange():
    """build_mood_prompt en namespace Cinéma : comportement historique complet."""
    import core.storyboard as sb
    from api.apercu import build_mood_prompt
    sb.set_namespace("storyboard")
    p = build_mood_prompt({"seedance_prompt": "a forest", "focal": "35mm",
                           "shot_size": "PL", "scene_title": "Marche en forêt"}, "")
    assert "35mm" in p and "wide shot" in p, "termes caméra Cinéma présents"
    assert "film grain" in p, "suffixe qualité Cinéma présent"
    assert "Marche en forêt" in p, "description d'action présente"
    assert "OPENING state" not in p, "pas de consigne keyframe Live côté Cinéma"


@test
def prompts_traduction_proteges():
    """core/lang.py : protection des dialogues §D0§ + tier utilitaire."""
    import core.lang as lang
    src = inspect.getsource(lang)
    assert "§D" in src, "marqueurs de protection des dialogues"
    assert 'tier="utility"' in src, "traduction sur le tier utilitaire"


# ══════════════════════════════════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    print(f"PANDORA | Cinéma — harnais de non-régression ({len(_TESTS)} tests)")
    print(f"Données temporaires : {_TMP}\n")
    ok, ko = 0, 0
    for fn in _TESTS:
        try:
            fn()
            print(f"  OK    {fn.__name__}")
            ok += 1
        except Exception as e:
            print(f"  ÉCHEC {fn.__name__} — {e}")
            traceback.print_exc()
            ko += 1
    print(f"\n{ok} OK · {ko} échec(s)")
    return 1 if ko else 0


if __name__ == "__main__":
    sys.exit(main())
