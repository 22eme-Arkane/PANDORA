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


@test
def refonte_interface():
    """Refonte UI 2026-06-12 (portée depuis Live) : nav en BARRE BASSE façon
    DaVinci, assistant à GAUCHE + colonne symétrique, Manuel/Contact en topbar,
    Paramètres centré, Studio IA sans trait doublé, bandeaux alignés 60 px."""
    import ui.pandora_window as PW
    src_sb = inspect.getsource(PW._Sidebar.__init__)
    assert "setFixedHeight(64)" in src_sb and "border-top" in src_sb, \
        "nav en barre basse (taskbar), plus de colonne latérale"
    assert "setFixedWidth(268)" not in inspect.getsource(PW), "colonne 268px retirée"
    src_nav = inspect.getsource(PW.NavItem.__init__)
    assert "QVBoxLayout" in src_nav, "items : icône au-dessus du libellé"
    src_init = inspect.getsource(PW.PandoraWindow.__init__)
    assert 'side="left"' in src_init, "assistant IA à gauche"
    assert "_right_spacer" in src_init, "colonne symétrique au bord droit"
    assert "header_height=60" in src_init, "en-tête assistant aligné sur les bandeaux"
    src_top = inspect.getsource(PW.PandoraWindow._build_global_topbar)
    assert "_btn_manual_top" in src_top and "_btn_contact_top" in src_top, \
        "Manuel + Nous contacter en haut à gauche"
    assert "255,79,106" in src_top and "37,211,102" in src_top, \
        "Manuel en ROUGE, Nous contacter en VERT"
    # Éditeur scénario : scrollbar au bord (marges document, pas padding CSS)
    from ui.page_scenario import PageScenario as _PSC
    src_ed = inspect.getsource(_PSC._build_editor)
    assert "setDocumentMargin" in src_ed and "padding:32px 120px" not in src_ed
    # Retours 2026-06-13 : t2v — dossier vidéos pleine largeur (ghost) avec la
    # barre DaVinci DESSOUS ; bouton centré avec le logo (spacer symétrique ×N)
    import ui.tab_t2v as _T2V
    src_t2v = inspect.getsource(_T2V)
    assert "lay.addWidget(self._btn_open_folder)" in src_t2v, "dossier pleine largeur"
    assert (src_t2v.index("lay.addWidget(self._btn_open_folder)")
            < src_t2v.index("lay.addWidget(self._davinci_bar)")), \
        "barre DaVinci sous le bouton dossier"
    assert "_sym_spacer" in src_t2v, "texte du bouton centré avec le logo PANDORA"
    # Nom UNIQUE du bouton de génération : « Lancer la file d'attente » partout
    import ui.tab_video_engines as _VE
    assert "▶  Générer" not in inspect.getsource(_VE), \
        "Génération directe : « Lancer la file d'attente »"
    src_pages = inspect.getsource(PW.PandoraWindow._build_pages)
    assert "setMaximumWidth(1360)" in src_pages and "_settings_wrap" in src_pages, \
        "Paramètres centré comme le Studio IA"
    assert "_settings_wrap" in inspect.getsource(PW.PandoraWindow._navigate)
    # Studio IA : trait unique + onglets formulaire plafonnés/centrés
    from ui.seedance_widget import SeedanceWidget
    src_sw = inspect.getsource(SeedanceWidget)
    assert "setDrawBase(False)" in src_sw, "pas de ligne de base doublée"
    assert "_clamp_content_width" in src_sw, "onglets formulaire plafonnés"
    assert "self.tab_t2v, self.tab_davinci, self.tab_engines" in src_sw, \
        "plafonnés : formulaires seulement (Vidéothèque/Historique pleine largeur)"
    # Bandeaux des pages au STANDARD 60 px (alignés avec l'assistant)
    from ui.page_storyboard import PageStoryboard as _PSB
    assert "setFixedHeight(60)" in inspect.getsource(_PSB._build_shots_topbar)


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
def prompts_nano_banana_qualite():
    """Suffixes Nano Banana (partagés Cinéma/Live) : qualité + contraintes intactes."""
    import api.nano_banana as nb
    # Améliorations 2026-06-10 : lumière/détail partout, ghost-mannequin pour HMC
    assert "ghost-mannequin" in nb._ITEM_LINE, "costumes/HMC en ghost-mannequin"
    assert "ultra-detailed" in nb._ITEM_LINE and "lighting" in nb._ITEM_LINE
    assert "ltra-detailed" in nb._DECOR_LINE, "qualité décors"
    for sfx in (nb._CLASSIC_PORTRAIT_SUFFIX, nb._ACTION_POSE_SUFFIX,
                nb._DUO_PORTRAIT_SUFFIX):
        assert "sharp focus" in sfx, "netteté portraits"
    # Contraintes historiques préservées
    assert "No person" in nb._ITEM_LINE and "white seamless background" in nb._ITEM_LINE
    assert "No people" in nb._DECOR_LINE and "NOT a white background" in nb._DECOR_LINE
    assert "3/4 front angle" in nb._VEHICLE_LINE, "angle véhicule préservé"


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
def moteurs_storyboard_filtres():
    """Générer depuis Storyboard : combo ouvert aux moteurs compatibles, t2v purs
    écartés ; libellés SANS « keyframes » (les keyframes de moods sont un
    mécanisme Live/Mapping — vérifié : aucun end_image_path en Cinéma) et
    Seedance 2.0 marqué « recommandé » (retour Matthieu 2026-06-13)."""
    import ui.tab_t2v as t2v
    src = inspect.getsource(t2v)
    assert "use_keyframes=False" in src, "combo filtré, libellés sans keyframes"
    assert 'recommended=("seedance-2.0",)' in src, "Seedance 2.0 recommandé"
    assert "end_image_path" not in src and "_get_mapping_keyframes" not in src, \
        "le Cinéma n'envoie JAMAIS de keyframes de moods"
    from core.engine_caps import sequence_engines
    pairs = sequence_engines(t2v._ENGINES, use_keyframes=False,
                             recommended=("seedance-2.0",))
    keys = [k for _, k in pairs]
    assert "veo-3.1" not in keys and "sora-2" not in keys, "t2v purs écartés"
    assert "kling-v3-pro" in keys and "seedance-2.0" in keys, "moteurs i2v ouverts"
    labels = dict((k, l) for l, k in pairs)
    assert "keyframes" not in " ".join(labels.values()), \
        "aucun libellé keyframes en Cinéma"
    assert "recommandé" in labels["seedance-2.0"], "« recommandé » sur Seedance 2.0"
    assert "raccord i2v" in labels["seedance-2.0"] and "réfs" in labels["seedance-2.0"]
    # Le Live, lui, garde l'affichage keyframes (raccords par moods)
    live_labels = dict((k, l) for l, k in sequence_engines(t2v._ENGINES))
    assert "keyframes" in live_labels["seedance-2.0"], "Live conserve keyframes"


@test
def refs_cinema_redimensionnees():
    """Analyse des références Cinéma : images redimensionnées avant envoi (fix 413)."""
    import api.screenplay as s
    src = inspect.getsource(s.AnalyzeReferencesWorker.run)
    assert "encode_image_for_vision" in src, "redimensionnement branché"
    # Bande de miniatures : défilement molette (fix 2026-06-11, partagé avec Live)
    from ui.page_scenario import PageScenario
    assert "WheelHScroller" in inspect.getsource(PageScenario._open_refs_window), \
        "molette → défilement horizontal des miniatures"


@test
def prompts_traduction_proteges():
    """core/lang.py : protection des dialogues §D0§ + tier utilitaire."""
    import core.lang as lang
    src = inspect.getsource(lang)
    assert "§D" in src, "marqueurs de protection des dialogues"
    assert 'tier="utility"' in src, "traduction sur le tier utilitaire"


@test
def bibliotheque_images_branchee():
    """Bibliothèque d'images globale : porte unique sur TOUS les points d'ajout Cinéma."""
    from ui.page_scenario import PageScenario
    assert "ImageLibraryDialog" in inspect.getsource(PageScenario._on_add_refs), \
        "refs du scénario via la bibliothèque"
    for mod_name in ("ui.dialog_character", "ui.dialog_decor", "ui.dialog_accessory",
                     "ui.dialog_hmc", "ui.dialog_vehicle", "ui.dialog_arrange_session"):
        mod = __import__(mod_name, fromlist=["_"])
        assert "ImageLibraryDialog" in inspect.getsource(mod), \
            f"{mod_name} : refs via la bibliothèque"
    # Templates Studio IA : ajout d'images via la bibliothèque (copie dans la catégorie)
    from ui.dialog_style_gallery import StyleGalleryDialog
    src = inspect.getsource(StyleGalleryDialog._on_add_image)
    assert "ImageLibraryDialog" in src and "copy2" in src, \
        "templates : choix via bibliothèque puis copie locale"
    # Moods : import d'une image perso (copiée dans le plan, activable comme mood)
    from ui.dialog_apercu import MoodDialog
    src = inspect.getsource(MoodDialog._import_image)
    assert "ImageLibraryDialog" in src and "save_apercus" in src and "copy2" in src, \
        "mood importable depuis la bibliothèque/disque"


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
