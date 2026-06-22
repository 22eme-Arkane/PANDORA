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
    """Paramètres Cinéma : sélecteur d'assistant IA (Claude/Fable 5/GPT-5.5/Mistral/Ollama)."""
    from ui.page_settings import SettingsPage
    p = SettingsPage()
    n = p.ai_combo.count()
    assert n == 8, "8 choix (PANDORA optimisé défaut, Sonnet, Haiku, Fable 5, GPT-5.5, Mistral, Ollama, Personnalisé)"
    labels = [p.ai_combo.itemText(i) for i in range(n)]
    assert "optimisé" in labels[0] and "défaut" in labels[0], "PANDORA optimisé = défaut (1er)"
    assert any("Fable 5" in x for x in labels), "Fable 5 proposé"
    assert any("GPT-5.5" in x for x in labels), "GPT-5.5 proposé"
    assert any("Choix personnalisé" in x for x in labels), "Choix personnalisé proposé"
    assert any("PANDORA optimisé" in x for x in labels), "PANDORA optimisé proposé"
    assert any("Mistral" in x for x in labels) and any("Ollama" in x for x in labels)
    # Clés GPT + Mistral présentes (menu déroulant facultatif)
    assert hasattr(p, "openai_input") and hasattr(p, "mistral_input")
    assert hasattr(p, "_opt_keys_box") and hasattr(p, "_btn_opt_keys"), "menu clés facultatives"
    # La sauvegarde écrit bien les clés de config IA + moteur par tâche
    src = inspect.getsource(SettingsPage.save)
    for key in ("ai_provider", "ai_model_creative", "openai_key", "mistral_key",
                "ollama_url", "ai_task_engines"):
        assert key in src, f"save() persiste {key}"
    # Réorganisation 2026-06-13 : Apparence → Assistant IA → Clés API →
    # Sauvegarder → DaVinci tout en bas ; testeurs en bleu à côté des liens
    # « Obtenir une clé » ; bouton Mises à jour retiré (déjà en topbar) ;
    # boutons d'aide = « ? » bien visible
    src_pg = inspect.getsource(__import__("ui.page_settings", fromlist=["_"]))
    assert "Vérifier les mises à jour" not in src_pg, "bouton Mises à jour retiré"
    assert (src_pg.index('_section("Assistant IA")')
            < src_pg.index('_section("Clés API")')), "Assistant IA avant les clés"
    # Sauvegarde AUTOMATIQUE : plus de bouton « Sauvegarder »
    assert 'QPushButton("Sauvegarder")' not in src_pg, "bouton Sauvegarder retiré"
    assert "_wire_autosave" in src_pg and "Sauvegarde automatique" in src_pg, "auto-save branché"
    # Défaut Opus 4.8 + preset PANDORA optimisé + bridge auto (bouton retiré)
    assert '"claude-opus-4-8"' in src_pg and "_apply_pandora_preset" in src_pg
    src_dv = inspect.getsource(__import__("ui.davinci_panel", fromlist=["_"]))
    assert "Installer le bridge" not in src_dv, "bouton Installer le bridge retiré (auto à l'install)"
    assert '_test_btn("✓  Tester API fal.ai"' in src_pg, "testeur fal.ai inline"
    assert '_test_btn("✓  Tester API Anthropic"' in src_pg, "testeur Anthropic inline"
    assert 'QPushButton("?")' in src_pg, "boutons d'aide « ? » lisibles"
    # Manuel : bouton Fermer en ROUGE avec son libellé
    src_man = inspect.getsource(__import__("ui.dialog_user_manual", fromlist=["_"]))
    assert '"Fermer" if self._lang == "fr" else "Close"' in src_man
    assert "rgba(255,79,106" in src_man.split("_close_btn = QPushButton")[1][:800], \
        "Fermer en rouge"


@test
def edition_cinema_only():
    """Build v1.2.0 : édition Cinéma seule détectée par core.edition ; main.py
    saute le sélecteur ; le splash masque « Retour » ; le .spec exclut le Live."""
    import core.edition as ed
    # En dev (live_window présent), l'édition complète reste active → chooser
    assert ed.is_cinema_only() is False, "dev = édition complète (Live présent)"
    # main.py : démarrage conditionnel, sans import statique du Live/chooser
    # hors de la branche dev
    src_main = open("main.py", encoding="utf-8").read()
    assert "from core.edition import is_cinema_only" in src_main
    assert "if _CINEMA_ONLY:" in src_main, "branche Cinéma directe"
    assert 'mode == "live" and not _CINEMA_ONLY' in src_main, "Live jamais ouvert en Cinéma"
    # Splash : bouton Retour optionnel (masqué en Cinéma seule)
    from PyQt6.QtWidgets import QApplication
    from ui.splash import SplashWindow
    assert "show_back" in inspect.getsource(SplashWindow.__init__)
    SplashWindow("cinema", show_back=False)   # ne doit pas lever
    # Le .spec exclut explicitement le Live (aucun module Live dans le build)
    spec = open("pandora.spec", encoding="utf-8").read()
    for mod in ("live_window", "ui.chooser", "resolume", "core.live_mapping",
                "api.resolume_push", "ui.tab_t2v_live"):
        assert f'"{mod}"' in spec, f".spec doit exclure {mod}"
    # Version bumpée
    from core.version import VERSION
    # Tolère un suffixe pré-release (« 1.2.0-bêta ») pour les builds de test.
    assert VERSION.split("-")[0] == "1.2.0", f"version attendue 1.2.0[-suffixe], lue {VERSION}"


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


@test
def studio_sound_design_upscaling():
    """Studio IA Cinéma : onglets Sound Design + Upscaling (portés du Live) —
    ordre après Génération directe, Vidéothèque branchée, AUCUN import Live."""
    import ui.seedance_widget as SW
    src = inspect.getsource(SW)
    assert (src.index("addTab(self.tab_engines")
            < src.index("addTab(self.tab_upscale")
            < src.index("addTab(self.tab_sound")
            < src.index("addTab(self.tab_library")), \
        "ordre : Génération directe → Upscaling → Sound Design → Vidéothèque"
    assert "set_library_provider(self.tab_library.list_all_clips)" in src, \
        "Upscaling relié à la Vidéothèque Cinéma"
    assert "self.tab_sound, self.tab_music, self.tab_upscale" in src, \
        "Sound Design + Musique IA + Upscaling plafonnés/centrés comme les autres formulaires"
    # Copies Cinéma : aucun IMPORT de fichier Live (séparation stricte)
    import ui.tab_upscale as UP
    import ui.tab_sound_design as SD
    for mod in (UP, SD):
        for line in inspect.getsource(mod).splitlines():
            if line.strip().startswith(("from ui.", "import ui.")):
                assert "_live" not in line, f"{mod.__name__} : import Live interdit"
    # Instanciation headless + invariants
    t = UP.TabUpscale()
    assert "Lancer la file d'attente" in t._btn_run.text(), "nom unique du bouton"
    assert t._btn_open.isEnabled(), "Ouvrir le dossier toujours actif"
    real = os.path.abspath(__file__)
    assert t.add_clips_from_paths([real, real]) == 1, "dédoublonnage de la file"
    assert "abandon_thread(self._worker)" in inspect.getsource(UP.TabUpscale._process_next), \
        "chaîne protégée (worker précédent parqué)"
    sd = SD.TabSoundDesign()
    assert "Lancer la file d'attente" in sd._btn_generate.text()
    assert sd._btn_open_dir.isEnabled()
    from ui.tab_video_library import TabVideoLibrary
    assert hasattr(TabVideoLibrary, "list_all_clips")
    # Menus déroulants portés du Live (retour 2026-06-13) : « Choisir les
    # références » et « Éléments récurrents » repliés par défaut dans t2v
    import ui.tab_t2v as _T2V2
    src_t2v2 = inspect.getsource(_T2V2)
    assert "_btn_style_toggle" in src_t2v2 and "_btn_casting_toggle" in src_t2v2, \
        "toggles Choisir les références + Éléments récurrents"
    assert "self._film_style_frame.setVisible(False)" in src_t2v2, "réfs repliées"
    assert "self._casting.setVisible(False)" in src_t2v2, "éléments repliés"
    # Création de personnage : défaut PORTRAIT classique, pas character sheet
    # 5 vues (retour 2026-06-13). La génération auto depuis scénario est déjà
    # en gen_mode="classic".
    from ui.dialog_character import CharacterDialog
    cd = CharacterDialog(None, {"name": "Test", "role": ""})
    assert cd._gen_mode_combo.currentData() == "classic", "défaut = portrait"
    assert cd._gen_mode_combo.itemData(0) == "classic", "portrait en 1er"
    src_sc2 = inspect.getsource(__import__("ui.page_scenario", fromlist=["_"]))
    assert 'gen_mode="classic"' in src_sc2, "génération auto en portrait classique"


# ══════════════════════════════════════════════════════════════════════════════
# Prompts Cinéma — enrichis mais FIDÈLES au scénario
# ══════════════════════════════════════════════════════════════════════════════

@test
def prompts_storyboard_cinema():
    import api.screenplay as s
    t = s._GENERATE_STORYBOARD_TMPL
    # Découpage en SECTIONS : l'IA renvoie des champs (action/staging/ambiance/
    # decor/lighting) assemblés en [🎬 ACTION]… par prompt_sections.build().
    for k in ('"action"', '"staging"', '"ambiance"', '"decor"', '"lighting"'):
        assert k in t, f"champ de section {k} dans le découpage"
    assert "hors champ" in t, "personnages hors champ exclus du découpage"
    assert "INTENTION d'éclairage" in t and "AUCUN projecteur" in t, "plan de feu = intention, pas de matériel visible"
    assert hasattr(s, "_technique_line"), "section Technique déterministe (champs caméra)"
    assert "prompt_sections" in inspect.getsource(s.GenerateStoryboardWorker.run), \
        "le worker assemble le prompt en sections"
    assert "duration" in t and "15.0" in t, "contrainte durée Seedance"
    # Sound design généré AVEC le storyboard (retour 2026-06-13, parité Live)
    assert '"sound_prompt"' in t, "le storyboard génère aussi un prompt sound design"
    assert "NO speech" in t and "SFX" in t, "sound_prompt = ambiance/SFX sans voix"
    # Persisté + champ dans le dialogue de plan ; bouton « Améliorer » Seedance
    # RETIRÉ provisoirement (Fable 5 dégrade), prompt Action conservé
    import core.storyboard as sb
    assert 'setdefault("sound_prompt"' in inspect.getsource(sb.save_shot)
    src_ds = inspect.getsource(__import__("ui.dialog_shot", fromlist=["_"]))
    assert "self._sound_prompt" in src_ds and "Prompt sound design" in src_ds, \
        "champ sound design dans le dialogue de plan"
    assert '"sound_prompt":      self._sound_prompt.toPlainText()' in src_ds, "sound_prompt sauvé"
    assert "self._btn_enhance_seedance = None" in src_ds, "Améliorer Seedance retiré"
    assert "_btn_enhance_action" in src_ds, "Améliorer Action conservé"
    # Mouvement caméra du storyboard INJECTÉ dans le prompt Seedance (Fixe = plan fixe
    # explicite, sinon le modèle dérive en travelling/grue).
    import core.camera_data as _cd
    assert hasattr(_cd, "shot_movement_to_prompt"), "mapping mouvement caméra → prompt"
    _fx = _cd.shot_movement_to_prompt("Fixe").lower()
    assert "static" in _fx and "no camera movement" in _fx, "Fixe = plan fixe explicite"
    assert _cd.shot_movement_to_prompt("Grue / Drone") and not _cd.shot_movement_to_prompt(""), "mapping mouvements"
    _t2v = inspect.getsource(__import__("ui.tab_t2v", fromlist=["_"]))
    assert _t2v.count("shot_movement_to_prompt(self._active_shot") >= 2, \
        "mouvement injecté dans l'envoi réel ET l'aperçu T2V"


@test
def colonne_langues_dialogues():
    """Colonne « Langues » (storyboard Cinéma) : choix par plan, défaut anglais ;
    dialogues traduits À L'ENVOI uniquement (pas dans le prompt affiché)."""
    import ui.page_storyboard as M
    assert len(M._COLS) == 19, "Langues (16) + Nom du plan (17) + boutons (18) = 19 colonnes"
    assert M._COLS[16][0] == "Langues" and M._COLS[17][0] == "Nom du plan" and M._COLS[18][0] == "", \
        "Langues en 16, Nom du plan en 17, boutons en 18"
    # « Nom du plan » (scene_title) s'affiche par défaut juste après « Plan » (logique 3)
    assert M._DEFAULT_COL_ORDER.index(17) == M._DEFAULT_COL_ORDER.index(3) + 1, \
        "Nom du plan affiché juste après Plan"
    # Séquence affichée « S<n> » (et non plus « SQ<n> »)
    rsrc = inspect.getsource(M._ShotRow.__init__)
    assert 'f"S{sq}"' in rsrc and 'f"SQ' not in rsrc, "libellé séquence = S<n>"
    assert 'scene_title' in rsrc, "colonne Nom du plan = scene_title"
    # Dialog d'édition : titre « S<n> — P<n> » + champ renommé « Nom du plan »
    dsrc = inspect.getsource(__import__("ui.dialog_shot", fromlist=["_"]))
    assert 'f"S{seq} — P{siq}"' in dsrc and '"Nom du plan"' in dsrc, \
        "dialog : titre S<n> + libellé Nom du plan"
    # défaut « en » persisté
    import core.storyboard as sb
    assert 'setdefault("dialogue_lang", "en")' in inspect.getsource(sb.save_shot)
    # liste de langues + anglais recommandé en tête
    from core.lang import DIALOGUE_LANGS, translate_dialogues_to, lang_label
    assert DIALOGUE_LANGS[0][1] == "en" and "recommand" in DIALOGUE_LANGS[0][0].lower()
    assert lang_label("en") == "Anglais"
    # traduction des dialogues = à l'ENVOI (api/real), pas dans le prompt à l'écran
    src_real = inspect.getsource(__import__("api.real", fromlist=["_"]))
    assert "translate_dialogues_to" in src_real and "dialogue_lang" in src_real
    # le prompt builder NE traduit PAS le dialogue (seulement à l'envoi)
    src_t2v = inspect.getsource(__import__("ui.tab_t2v", fromlist=["_"]))
    assert '"dialogue_lang":' in src_t2v, "params transporte dialogue_lang"
    # translate_dialogues_to ne touche QUE les guillemets : sans guillemets =
    # no-op déterministe (aucun appel réseau)
    assert translate_dialogues_to("texte sans aucun dialogue", "fr") == "texte sans aucun dialogue"
    assert translate_dialogues_to("", "fr") == ""


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
    """Aucune fonctionnalité Live n'a fui dans les fichiers Cinéma.
    (Le sound_prompt n'est PLUS un marqueur Live : depuis 2026-06-13 le storyboard
    Cinéma le génère aussi — parité voulue. On vérifie ici les marqueurs propres
    au Live qui ne doivent pas exister côté Cinéma : masquage de colonnes, musique.)"""
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
def decor_sept_vues():
    """Décors : option « 7 vues de la pièce » — 6 faces (sol, plafond, gauche,
    droite, avant, arrière) PUIS un 7e plan d'ensemble qui les regroupe ;
    cohérence spatiale stricte ; worker dédié + combo de mode + option depuis
    le scénario (dialog d'extraction)."""
    from core.room_views import (SIX_FACES, build_six_view_prompts,
                                  build_overview_prompt, build_seven_view_prompts)
    assert len(SIX_FACES) == 6
    codes = {c for _, c, _ in SIX_FACES}
    assert codes == {"sol", "plafond", "gauche", "droite", "avant", "arriere"}
    six = build_six_view_prompts("salle à manger chaleureuse")
    assert len(six) == 6
    seven = build_seven_view_prompts("salle à manger chaleureuse")
    assert len(seven) == 7, "6 faces + 1 plan d'ensemble"
    # La 7e vue est le plan d'ensemble et arrive en DERNIER.
    o_label, o_code, o_prompt = seven[-1]
    assert o_code == "ensemble" and "ENTIRE room" in o_prompt
    assert o_code == build_overview_prompt("x")[1]
    for label, code, p in seven:
        assert "salle à manger" in p and "strict spatial consistency" in p
    # worker dédié — émet une liste structurée (1 entrée par vue)
    from api.nano_banana import GenerateRoomViewsWorker
    w = GenerateRoomViewsWorker("salle à manger", "Salle à manger")
    assert hasattr(w, "views_finished"), "signal structuré (label/code/path) par vue"
    # Les 7 vues deviennent 7 DÉCORS distincts d'une même pièce (room_group),
    # regroupés dans un bandeau dépliable (page Décors) — voir aussi
    # decors_sept_vues_groupees.
    import inspect
    src = inspect.getsource(__import__("ui.dialog_decor", fromlist=["_"]))
    assert '"seven_views"' in src and "GenerateRoomViewsWorker" in src
    assert "_on_room_decors_done" in src and "room_group" in src, \
        "la fiche décor crée 7 décors frères marqués room_group"
    # Mode « Image unique » par défaut + confirmation avant les 7 vues.
    assert "setCurrentIndex(0)" in src, "mode image unique par défaut dans la fiche décor"
    assert "Générer les 7 vues de la pièce" in src, "confirmation avant les 7 vues"
    # Chaque vue stocke SON prompt (cadrage) → régénération fidèle.
    nb = inspect.getsource(GenerateRoomViewsWorker._real)
    assert '"prompt": fprompt' in nb, "le worker renvoie le prompt par vue"
    # Disponible aussi depuis le scénario (« Générer les décors ») → 7 décors frères.
    eg = inspect.getsource(__import__("ui.dialog_extract_generate", fromlist=["_"]))
    assert "offer_room_views=True" in eg and "views_finished" in eg
    assert "room_group" in eg, \
        "depuis le scénario : 7 vues → 7 décors d'une pièce (room_group)"
    # COHÉRENCE des 6 faces : chaque face est une ÉDITION NB2 qui INJECTE le plan
    # d'ensemble + le plan d'architecture comme RÉFÉRENCES (même pièce, angles
    # différents) ; repli TEXTE robuste (4 essais, backoff) si l'édition échoue.
    assert "ref_urls" in nb and "_gen_edit" in nb and "consistency" in nb, \
        "faces générées par édition avec références (plan d'ensemble + plan d'archi)"
    assert "ov_path" in nb and "fp_path" in nb, "réfs = plan d'ensemble + plan d'architecture"
    assert "edit_off" in nb and "range(4)" in nb, "repli texte robuste (4 essais)"
    assert "pandora_decor.log" in nb, "journal de diagnostic des 7 vues"
    assert "_VIEW_GAP_S" in nb, "génération ÉTAPE PAR ÉTAPE (vues espacées dans le temps)"
    assert "_faces_ok" in nb and "_last_error" in nb, "worker remonte les faces manquantes"
    assert hasattr(w, "_faces_ok") and hasattr(w, "_last_error"), "attributs de diagnostic présents"
    assert "_room_warnings" in eg and "Vues manquantes" in eg, \
        "dialogue : avertissement consolidé des faces manquantes"
    # Identifier+générer depuis le scénario : image unique (portrait), pas 5 vues.
    assert 'gen_mode="classic"' in eg and 'gen_mode="sheet_5views"' not in eg, \
        "personnages : portrait unique par défaut depuis le scénario"


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


@test
def synchronisation_multi_options():
    """Synchronisation Storyboard : fenêtre multi-options (réassigner noms /
    réécrire prompts / re-synchroniser décors / réécrire scénario), preview,
    worker piloté par options + worker de réécriture de scénario (nouvelle version)."""
    from ui.dialog_storyboard_sync import StoryboardSyncConfirmDialog, StoryboardSyncDialog

    # 1) La fenêtre de confirmation expose les options ; défauts cohérents.
    dlg = StoryboardSyncConfirmDialog(3)
    opts = dlg.selected_options()
    assert set(opts) == {"reassign", "rewrite_prompts", "resync_decors", "rewrite_scenario",
                         "sync_staging", "sync_lighting"}, \
        "options de synchronisation (dont mise en scène + plan de feu)"
    assert opts["reassign"] and opts["rewrite_prompts"], "réassigner + prompts cochés par défaut"
    assert not opts["resync_decors"] and not opts["rewrite_scenario"], \
        "décors + scénario décochés par défaut"
    assert not opts["sync_staging"] and not opts["sync_lighting"], \
        "mise en scène + plan de feu décochés par défaut"
    assert hasattr(dlg, "selected_options")

    # 2) Le worker de sync honore un dict d'options (phases gated).
    from api.screenplay import SyncStoryboardWorker
    w = SyncStoryboardWorker([], {"reassign": True, "rewrite_prompts": False,
                                  "resync_decors": False})
    assert w._opt_reassign and not w._opt_prompts and not w._opt_decors, \
        "options propagées au worker"

    # 3) Worker de réécriture du scénario depuis le storyboard.
    from api.screenplay import RewriteScreenplayFromStoryboardWorker
    rw = RewriteScreenplayFromStoryboardWorker([])
    assert hasattr(rw, "finished") and hasattr(rw, "failed")

    # 4) Le dialog principal accepte les options et sauvegarde le scénario en
    #    NOUVELLE version (non destructif).
    src = inspect.getsource(StoryboardSyncDialog)
    assert "rewrite_scenario" in src and "_save_scenario_version" in src, \
        "branche scénario dans le dialog"
    assert '"versions"' in src and "save_scenario" in src, \
        "sauvegarde en nouvelle version (jamais d'écrasement)"


@test
def storyboard_chat_ia():
    """Chat Storyboard : panneau droit repliable (poignée CHAT), worker connecté
    à l'IA sélectionnée, lit tout le storyboard, éditions CHIRURGICALES sur liste
    blanche de champs ; fermé par défaut, branché dans la page."""
    # Worker
    from api.screenplay import StoryboardChatWorker, STORYBOARD_CHAT_FIELDS, _STORYBOARD_CHAT_SYSTEM
    assert "seedance_prompt" in STORYBOARD_CHAT_FIELDS and "scene_title" in STORYBOARD_CHAT_FIELDS
    w = StoryboardChatWorker("bonjour", [{"id": "1", "number": "1"}])
    assert hasattr(w, "finished") and hasattr(w, "failed")
    # Le system prompt impose la chirurgie + le format JSON edits/reply.
    assert "CHIRURGIE STRICTE" in _STORYBOARD_CHAT_SYSTEM
    assert '"edits"' in _STORYBOARD_CHAT_SYSTEM and '"reply"' in _STORYBOARD_CHAT_SYSTEM

    # Panneau + poignée
    from ui.storyboard_chat import StoryboardChatPanel, StoryboardChatToggleStrip
    panel = StoryboardChatPanel(shots_provider=lambda: [], on_applied=None)
    strip = StoryboardChatToggleStrip(panel)
    assert hasattr(panel, "_apply_edits")
    # L'application filtre sur la liste blanche (pas d'écriture hors champs autorisés).
    src = inspect.getsource(StoryboardChatPanel._apply_edits)
    assert "STORYBOARD_CHAT_FIELDS" in src and "save_shot" in src

    # Branché au niveau APPLICATION (miroir de l'assistant IA), fermé par défaut,
    # actif uniquement sur la page Storyboard.
    wsrc = inspect.getsource(__import__("ui.pandora_window", fromlist=["_"]))
    assert "StoryboardChatPanel" in wsrc and "StoryboardChatToggleStrip" in wsrc
    assert "_sb_chat_panel.setVisible(False)" in wsrc, "chat fermé par défaut"
    assert "_update_sb_chat" in wsrc and 'key == "storyboard"' in wsrc, \
        "chat affiché seulement sur la page Storyboard (symétrie spacer sinon)"
    # La page expose le rafraîchissement appelé par le chat.
    psrc = inspect.getsource(__import__("ui.page_storyboard", fromlist=["_"]))
    assert "_on_chat_applied" in psrc


@test
def pas_de_verif_solde():
    """Le bouton « Lancer la file d'attente » lance directement la génération —
    plus de garde-fou « Vérification du solde… » avant de partir."""
    import inspect
    for mod_name in ("ui.tab_t2v", "ui.tab_t2v_live"):
        src = inspect.getsource(__import__(mod_name, fromlist=["_"]))
        assert "btn_generate.clicked.connect(self.start_generation)" in src, \
            f"{mod_name} : le bouton lance directement la file"
        assert "btn_generate.clicked.connect(self._start_with_credit_check)" not in src, \
            f"{mod_name} : plus de vérification du solde sur le bouton"


@test
def moteurs_ia_par_tache():
    """Intégration moteurs : GPT-5.5 (OpenAI) ajouté ; moteur IA paramétrable
    PAR TÂCHE sans dégrader le défaut ; appels câblés avec task=."""
    import core.ai_provider as ap
    assert "openai" in ap._PROVIDERS
    assert set(ap.ENGINES) == {"claude", "opus", "haiku", "fable5", "gpt", "mistral", "ollama"}
    assert ap.ENGINES["gpt"]["provider"] == "openai"
    assert ap.ENGINES["opus"]["creative_model"] == "claude-opus-4-8"
    # Profil PANDORA optimisé (défaut) : moteur IDÉAL par tâche — Opus UNIQUEMENT
    # pour le storyboard, Sonnet pour scénario/sync, Haiku pour le reste (économe).
    assert ap.PANDORA_OPTIMIZED["storyboard_gen"] == "opus", "storyboard = Opus"
    assert ap.PANDORA_OPTIMIZED["extraction"] == "haiku", "extraction = Haiku (pas Opus)"
    assert ap.PANDORA_OPTIMIZED["screenplay"] == "claude", "scénario = Sonnet"
    assert not all(v == "opus" for v in ap.PANDORA_OPTIMIZED.values()), "plus Opus partout"
    keys = [t[0] for t in ap.TASKS]
    for k in ("enhance", "storyboard_chat", "assistant", "storyboard_gen",
              "screenplay", "extraction", "sync"):
        assert k in keys, f"tâche {k} paramétrable"
    # Défaut inchangé (non régression)
    assert ap._resolve_engine() == ("anthropic", "claude-opus-4-8")
    # Override par tâche
    orig = ap._cfg
    ap._cfg = lambda: {"ai_provider": "anthropic", "ai_model_creative": "claude-sonnet-4-6",
                       "ai_task_engines": {"enhance": "gpt", "storyboard_chat": "fable5"}}
    try:
        assert ap._resolve_engine("enhance") == ("openai", "")
        assert ap._resolve_engine("storyboard_chat") == ("anthropic", "claude-fable-5")
        assert ap._resolve_engine("assistant") == ("anthropic", "claude-sonnet-4-6")
        assert ap._model("creative", "openai") == "gpt-5.5"
    finally:
        ap._cfg = orig
    # Choix personnalisé : global "custom" → repli Anthropic Sonnet ; overrides actifs
    ap._cfg = lambda: {"ai_provider": "custom", "ai_model_creative": "",
                       "ai_task_engines": {"enhance": "opus"}}
    try:
        assert ap._resolve_engine() == ("anthropic", "claude-opus-4-8")
        assert ap._resolve_engine("enhance") == ("anthropic", "claude-opus-4-8")
    finally:
        ap._cfg = orig
    # Appels câblés avec task=
    sp = inspect.getsource(__import__("api.screenplay", fromlist=["_"]))
    for t in ('task="storyboard_chat"', 'task="storyboard_gen"', 'task="sync"',
              'task="screenplay"', 'task="extraction"'):
        assert t in sp, f"{t} câblé dans screenplay"
    assert 'task="enhance"' in inspect.getsource(__import__("api.enhance", fromlist=["_"]))
    assert 'task="assistant"' in inspect.getsource(__import__("api.assistant", fromlist=["_"]))
    # Paramètres : clés + testeurs GPT/Mistral + menu avancé par tâche
    src_pg = inspect.getsource(__import__("ui.page_settings", fromlist=["_"]))
    assert '_test_btn("✓  Tester API GPT-5.5"' in src_pg and '_test_btn("✓  Tester API Mistral"' in src_pg
    assert "Paramètres avancés" in src_pg and "_task_combos" in src_pg
    # Clés obligatoires (rouge) vs facultatives (menu déroulant bleu)
    assert '_badge("Obligatoire", "req")' in src_pg and '_badge("Facultatif", "opt")' in src_pg
    assert "Clés API facultatives" in src_pg
    # Description avancés : PANDORA optimisé Fable 5
    assert "optimisé avec Fable 5" in src_pg
    # Choix personnalisé câblé sur le moteur par tâche
    assert '"custom"' in src_pg and "_set_advanced" in src_pg


@test
def synchro_decor_meme_axe():
    """Studio IA / RENDU & AUDIO : option « Synchroniser le décor (même axe) » —
    fige le fond d'un plan généré (perso retiré par IA) et le réutilise comme
    référence décor pour les plans du même décor + même axe."""
    # Store par (décor, axe)
    import core.decor_sync as ds
    assert ds.get_synced_bg("", "") is None
    assert ds.get_synced_bg("salon", "Face") is None  # rien au départ
    assert hasattr(ds, "set_synced_bg") and hasattr(ds, "get_synced_bg")
    # Worker de nettoyage de fond (efface perso + reconstruit la pièce, NB2 edit)
    from api.nano_banana import CleanBackgroundWorker
    w = CleanBackgroundWorker("inexistant.png")
    assert hasattr(w, "finished") and hasattr(w, "failed")
    src = inspect.getsource(CleanBackgroundWorker)
    assert "nano-banana-2/edit" in src and "Remove ALL people" in src
    # Branché dans le Studio IA (toggle + capture + réinjection) — Cinéma
    t = inspect.getsource(__import__("ui.tab_t2v", fromlist=["_"]))
    assert "Synchroniser le décor (même axe)" in t, "toggle dans RENDU & AUDIO"
    assert "_maybe_capture_decor_bg" in t and "CleanBackgroundWorker" in t
    assert "get_synced_bg" in t, "réinjection du fond figé comme réf décor"


@test
def mise_en_scene_plan_de_feu():
    """Mise en scène & Plan de feu : plans vus de dessus éditables (caméra/acteurs/
    éléments puis lumières), record partagé par plan, axe caméra dérivé, intégration
    nav (groupes Scénario/Storyboard et Image&Son/Doublage) + synchro des prompts."""
    import core.staging as st
    # Modèle + axe caméra dérivé de l'angle
    assert st.axis_from_angle(0) == "Face" and st.axis_from_angle(180) == "Dos"
    assert st.axis_from_angle(90) == "Latéral 90°"
    rec = st.get("zz")
    assert "camera" in rec and "actors" in rec and "lights" in rec
    assert st.PROJECTOR_TYPES, "types de projecteurs définis"
    # Worker plan d'architecte vu de dessus
    from api.nano_banana import GenerateFloorPlanWorker
    w = GenerateFloorPlanWorker("salon", "Salon")
    assert hasattr(w, "finished")
    fp = inspect.getsource(GenerateFloorPlanWorker._real) if hasattr(GenerateFloorPlanWorker, "_real") \
        else inspect.getsource(GenerateFloorPlanWorker)
    assert "TOP-DOWN" in fp
    # Pages + canevas éditable
    from ui.page_staging import PageStaging, PageLighting
    assert PageStaging.MODE == "staging" and PageLighting.MODE == "lighting"
    cv = inspect.getsource(__import__("ui.staging_canvas", fromlist=["_"]))
    assert "ItemIsMovable" in cv and "add_actor" in cv and "add_light" in cv and "rotate_selected" in cv
    # Nav : intégrées dans les bons groupes
    wsrc = inspect.getsource(__import__("ui.pandora_window", fromlist=["_"]))
    assert '"mise_en_scene"' in wsrc and '"plan_de_feu"' in wsrc
    assert wsrc.index('"storyboard"') < wsrc.index('"mise_en_scene"'), "Mise en scène après Storyboard"
    assert wsrc.index('"camera"') < wsrc.index('"plan_de_feu"') < wsrc.index('"doublage"'), \
        "Plan de feu entre Image & Son et Doublage"
    # Synchro des prompts : tient compte de la mise en scène
    sp = inspect.getsource(__import__("api.screenplay", fromlist=["_"]))
    assert "mise_en_scene" in sp and "import core.staging" in sp


@test
def studio_musique_ia_et_image_ia():
    """Studio IA : onglets « Musique IA » (multi-moteurs fal.ai, défaut = le plus
    performant) et « Image IA » (panneau Studio Images partagé, source unique)."""
    import ui.seedance_widget as SW
    src = inspect.getsource(SW)
    # Ordre groupé : … Upscaling (fin G1) → Sound Design → Musique IA (G2) → Image IA (G3)
    assert (src.index("addTab(self.tab_upscale")
            < src.index("addTab(self.tab_sound")
            < src.index("addTab(self.tab_music")
            < src.index("addTab(self.tab_image")), \
        "ordre groupé : Upscaling → Sound Design → Musique IA → Image IA"
    # Barre d'onglets groupée : trait vertical en fin de groupe (façon dashboard)
    assert "_GroupedTabBar" in src and "set_group_ends" in src, \
        "barre d'onglets avec séparateurs de groupes"
    assert "set_group_ends({3, 5, 6})" in src, \
        "traits après Upscaling (G1), Musique IA (G2), Image IA (G3)"

    # ── Musique IA : catalogue multi-moteurs + défaut performant ──────────────
    import api.music as M
    assert len(M.MUSIC_ENGINES) >= 5, "plusieurs moteurs musique"
    assert M.default_engine() in M.MUSIC_ENGINES, "défaut valide"
    assert M.MUSIC_ENGINES[M.default_engine()].get("default"), "un moteur marqué défaut"
    # Tous les endpoints sont des modèles fal.ai
    for k, spec in M.MUSIC_ENGINES.items():
        assert "/" in spec["endpoint"], f"endpoint fal.ai pour {k}"
    # Worker : mock sans clé (finished(\"\")), pas d'appel réseau
    w = M.MusicWorker(M.default_engine(), "epic orchestral score", duration=20)
    assert hasattr(w, "finished") and hasattr(w, "failed")
    assert "fal_client.subscribe" in inspect.getsource(M.MusicWorker._real), "appel réel fal.ai"
    # Onglet UI instanciable, moteur par défaut sélectionné
    from ui.tab_music import TabMusic
    tm = TabMusic()
    assert tm._engine.currentData() == M.default_engine(), "défaut pré-sélectionné dans l'UI"
    assert tm._engine.count() == len(M.ENGINE_ORDER), "tous les moteurs listés"
    # Durée : tirette (slider) + saisie directe SYNCHRONISÉES
    from PyQt6.QtWidgets import QSlider, QSpinBox
    assert isinstance(tm._dur_slider, QSlider) and isinstance(tm._duration, QSpinBox), \
        "tirette + saisie de durée"
    tm._dur_slider.setValue(40)
    assert tm._duration.value() == 40, "saisie suit la tirette"
    tm._duration.setValue(25)
    assert tm._dur_slider.value() == 25, "tirette suit la saisie"
    # Aucun import de fichier Live (séparation stricte)
    for line in inspect.getsource(__import__("ui.tab_music", fromlist=["_"])).splitlines():
        if line.strip().startswith(("from ui.", "import ui.")):
            assert "_live" not in line, "tab_music : import Live interdit"

    # ── Image IA : panneau Studio Images partagé (source unique) ──────────────
    from ui.tab_image import TabImage
    ti = TabImage()
    assert ti.panel is not None, "StudioImagesPanel chargé dans l'onglet"
    assert type(ti.panel).__name__ == "StudioImagesPanel", "même classe que l'app autonome"
    # Discussion Claude repliable à droite, présentée comme le chat Storyboard :
    # FERMÉE par défaut + en-tête (✦ titre + ✕ effacer).
    assert hasattr(ti.panel, "_chat_panel") and hasattr(ti.panel, "_chat_toggle"), \
        "chat Claude repliable à droite"
    tog = ti.panel._chat_toggle
    assert tog._open is False, "discussion fermée par défaut (comme Storyboard)"
    assert hasattr(ti.panel, "_clear_chat"), "bouton effacer la conversation (en-tête)"

    # Réglages Image IA : Annuler + chargement masqués au repos ; aperçu TOUJOURS
    # visible (placeholder) pour garder la mise en page compacte.
    pn = ti.panel
    assert hasattr(pn, "_cancel_btn") and hasattr(pn, "_res_value"), "Annuler + résolution dérivée"
    assert pn._progress.isHidden() and pn._cancel_btn.isHidden(), \
        "barre de chargement / Annuler masqués tant qu'inactif"
    assert not pn._preview.isHidden() and "attente" in pn._preview.text().lower(), \
        "aperçu visible avec placeholder (évite les trous)"
    # Résolution : le combo 4K/2K/1K est SUPPRIMÉ (doublon avec la taille). Largeur
    # et Hauteur sont TOUJOURS visibles, saisie directe sans flèches (NoButtons), et
    # un template les pré-remplit. Les menus déroulants s'ouvrent vers le bas.
    from PyQt6.QtWidgets import QAbstractSpinBox as _QASB
    assert not hasattr(pn, "_res"), "combo de résolution retiré (doublon)"
    assert pn._cw.buttonSymbols() == _QASB.ButtonSymbols.NoButtons, "Largeur sans flèches"
    assert pn._ch.buttonSymbols() == _QASB.ButtonSymbols.NoButtons, "Hauteur sans flèches"
    assert type(pn._format).__name__ == "DownComboBox", "templates : menu déroulant vers le bas"
    pn._format.setCurrentIndex(pn._format.findData("logo_sq"))   # Logo carré 1024×1024
    assert (pn._cw.value(), pn._ch.value()) == (1024, 1024), "template pré-remplit Largeur/Hauteur"
    assert pn._target_size() == (1024, 1024) and pn._res_value() == "1K", \
        "Largeur/Hauteur = source de vérité de la taille + du palier"
    # Chargement : la barre GAUCHE est réservée à la génération (prompt + image) ;
    # la discussion charge dans le chat (_chat_busy), pas dans la fenêtre Image IA.
    assert hasattr(pn, "_chat_busy") and hasattr(pn, "_set_chat_busy"), "indicateur de chat dédié"
    assert pn._chat_busy.isHidden(), "indicateur de chat masqué au repos"
    assert "_set_chat_busy" in inspect.getsource(type(pn)._do_send), "le chat charge dans le chat"
    assert "_set_busy(True" not in inspect.getsource(type(pn)._do_send), \
        "le chat ne déclenche PAS la barre gauche"
    assert "_set_busy(True" in inspect.getsource(type(pn)._generate), "génération image → barre gauche"
    assert "_set_busy(True" in inspect.getsource(type(pn)._synth_prompt), "génération prompt → barre gauche"
    # Sauvegarder/Ouvrir déplacés À CÔTÉ du « Moteur de génération » (barre du haut
    # supprimée) + colonne de génération SCROLLABLE (plus rien de cropé).
    assert not hasattr(pn, "_build_topbar"), "barre supérieure supprimée"
    assert hasattr(pn, "_btn_img_save") and hasattr(pn, "_btn_img_open"), "boutons Save/Open présents"
    so = inspect.getsource(type(pn)._build_save_open_buttons)
    assert "Clés API" not in so, "pas de bouton Clés API"
    assert "_on_save_session" in so and "_on_open_session" in so, "Sauvegarder/Ouvrir Image IA"
    bl = inspect.getsource(type(pn)._build_left)
    assert "_build_save_open_buttons()" in bl and "MOTEUR DE GÉNÉRATION" in bl, \
        "Save/Open dans l'en-tête du moteur de génération"
    init_src = inspect.getsource(type(pn).__init__)
    assert "left_scroll" in init_src and "setWidgetResizable(True)" in init_src, \
        "colonne de génération scrollable (anti-crop)"
    # Simule un clic gauche sur la poignée → ouvre la discussion (fermée par défaut)
    from PyQt6.QtCore import Qt as _Qt
    tog.mousePressEvent(type("E", (), {"button": lambda s: _Qt.MouseButton.LeftButton})())
    assert tog._open is True and not ti.panel._chat_panel.isHidden(), "s'ouvre au clic"


@test
def decors_plan_auto_et_sync():
    """Plan vu de dessus stocké PAR DÉCOR (source unique) : auto-généré à la
    création/identification des décors, affiché dans « Plan des décors », réutilisé
    par Mise en scène ET Plan de feu (qui montre aussi caméra + acteurs)."""
    import core.decors as d
    # Champ floor_plan + helpers
    assert hasattr(d, "set_floor_plan") and hasattr(d, "floor_plan_for_shot")
    src_save = inspect.getsource(d.save_decor)
    assert '"floor_plan"' in src_save or "'floor_plan'" in src_save, "défaut floor_plan"

    # Worker batch
    from api.nano_banana import GenerateFloorPlansWorker, GenerateRoomViewsWorker
    assert hasattr(GenerateFloorPlansWorker, "plan_done")

    # Pipeline 7 vues raccord : plan d'ensemble → plan d'architecture (contexte)
    # → 6 faces en injectant ces références (NB2 edit).
    rv = inspect.getsource(GenerateRoomViewsWorker._real)
    assert "build_overview_prompt" in rv and "_floor_plan_prompt" in rv, "ensemble + architecture"
    assert "is_floor_plan" in rv, "plan d'architecture renvoyé séparément"
    assert "nano-banana-2/edit" in rv and "image_urls" in rv, "faces avec références injectées"
    assert rv.index("build_overview_prompt(base_en)") < rv.index("build_six_view_prompts(base_en)"), \
        "plan d'ensemble AVANT les 6 faces"

    # Auto-génération depuis le scénario (décors uniquement)
    eg = inspect.getsource(__import__("ui.dialog_extract_generate", fromlist=["_"]))
    assert "_auto_floor_plans = True" in eg, "auto plans activé pour les décors"
    assert "_maybe_start_floor_plans" in eg and "set_floor_plan" in eg

    # Page Décors : section « Plan des décors » synchronisée
    import ui.page_decors as PD
    pdsrc = inspect.getsource(PD)
    assert "_build_floor_plans_section" in pdsrc and "Plan des décors" in pdsrc
    assert "floor_plan" in pdsrc, "lit le plan du décor (source unique)"

    # « Créer un décor » génère le plan EN MÊME TEMPS que le décor (manuel aussi)
    dd = inspect.getsource(__import__("ui.dialog_decor", fromlist=["_"]))
    assert "GenerateFloorPlanWorker" in dd and "_maybe_gen_floor_plan" in dd, \
        "plan vu de dessus généré à la création manuelle du décor"
    assert dd.count("_maybe_gen_floor_plan()") >= 2, "appelé après image simple ET sheet"

    # Mise en scène / Plan de feu : lisent le plan du décor (par plan, via sélecteur)
    ps = inspect.getsource(__import__("ui.page_staging", fromlist=["_"]))
    assert "floor_plan_for_shot" in ps, "Mise en scène lit le plan du décor"
    assert "plan_decor_id" in ps, "sélecteur du plan de décor par plan"
    assert "_sync_decors" in ps, "synchro storyboard → plans (remplace Générer le plan)"
    # Régénération du plan d'architecte quand le décor (prompt) CHANGE
    assert "floor_plan_prompt" in dd, "régénère le plan si le décor change (prompt)"
    # Clic sur le plan d'architecte (page Décors) → aperçu en grand dans une fenêtre
    assert "_open_plan_preview" in pdsrc and "Cliquer pour agrandir" in pdsrc, \
        "clic sur le plan → aperçu en grand"
    # Clic droit sur un plan (liste gauche) → changer le plan du décor
    assert "_set_plan_decor_for" in ps and "Changer le plan du décor" in ps, \
        "clic droit liste → changer le plan du décor"

    # Plan de feu montre caméra + acteurs (référence non éditable)
    from ui.staging_canvas import StagingCanvas
    cv = StagingCanvas(mode="lighting")
    rec = {"plan_image": "", "camera": {"x": 0.5, "y": 0.8, "angle": 0.0},
           "actors": [{"name": "Jean", "x": 0.3, "y": 0.5}], "props": [], "lights": []}
    cv.load(rec)
    from ui.staging_canvas import _Token
    refs = [it for it in cv._scene.items()
            if isinstance(it, _Token) and getattr(it, "reference", False)]
    assert len(refs) >= 2, "caméra + acteurs visibles en Plan de feu"

    # « Tout supprimer » : Plan de feu vide les projecteurs, GARDE les réfs (acteurs)
    rec["lights"] = [{"name": "Key", "type": "key", "x": 0.5, "y": 0.3, "angle": 180.0}]
    cv.load(rec); cv.clear_all()
    assert rec["lights"] == [] and rec["actors"], "Plan de feu : projecteurs vidés, réfs gardées"
    # Mise en scène : vide acteurs + accessoires
    cvs = StagingCanvas(mode="staging")
    recs = {"plan_image": "", "camera": {"x": 0.5, "y": 0.8, "angle": 0.0},
            "actors": [{"name": "A", "x": 0.3, "y": 0.5}],
            "props": [{"name": "P", "x": 0.6, "y": 0.5}], "lights": []}
    cvs.load(recs); cvs.clear_all()
    assert recs["actors"] == [] and recs["props"] == [], "Mise en scène : acteurs/accessoires vidés"


@test
def staging_outils_projecteurs_sections():
    """Mise en scène / Plan de feu : rotation directe (poignée + mode + R),
    clic droit (acteur / projecteur), catalogue de projecteurs Famille→modèles,
    et prompt structuré en sections + toggles de synchro (son non envoyé)."""
    # Catalogue projecteurs
    import core.projectors as pr
    assert pr.families() and pr.models("led_panel"), "catalogue famille → modèles"
    assert any("SkyPanel" in m for m in pr.models("led_panel"))
    assert any("Titan" in m for m in pr.models("tube"))
    # Réglages du projecteur — capacités RÉELLES par modèle (d'après les specs)
    assert pr.capabilities("led_panel", "ARRI SkyPanel S60-C")["color"] == "full"
    assert pr.capabilities("cob", "Aputure LS 600d Pro")["color"] == "daylight"
    assert pr.capabilities("cob", "Aputure LS 600x Pro")["color"] == "bicolor"
    assert pr.capabilities("fresnel", "ARRI 650 (tungstène)")["color"] == "tungsten"
    assert pr.capabilities("fresnel", "ARRI L7-C (LED)")["color"] == "full"
    assert pr.capabilities("profile", "ETC Source Four 26°")["beam"] == (26, 26), "faisceau ellipsoïdale = degré du nom"
    assert pr.GEL_PRESETS and hasattr(pr, "describe_settings") and hasattr(pr, "default_settings")
    _d = pr.describe_settings({"family": "led_panel", "model": "ARRI SkyPanel S60-C",
                               "settings": {"intensity": 80, "cct": 4300}})
    assert "80 %" in _d and "4300 K" in _d, "réglages décrits pour le prompt"
    # Hauteur · inclinaison · louver · on/off · effets dynamiques (LED couleur)
    assert pr.capabilities("led_panel", "ARRI SkyPanel S60-C")["effects"] is True
    assert pr.capabilities("fresnel", "ARRI 650 (tungstène)")["effects"] is False
    assert pr.capabilities("practical", "Bougie / flamme")["louver"] is False
    assert pr.EFFECTS and any(c == "police" for c, _, _ in pr.EFFECTS)
    _ds = pr.default_settings("led_panel", "ARRI SkyPanel S60-C")
    for k in ("on", "height", "tilt", "louver", "effect"):
        assert k in _ds, f"réglage {k}"
    _dfx = pr.describe_settings({"family": "led_panel", "model": "ARRI SkyPanel S60-C",
                                 "settings": {"on": True, "effect": "police", "height": 3, "tilt": 45}})
    assert "EFFET" in _dfx and "10000 K" not in _dfx, "un effet REMPLACE la couleur statique"
    assert "3 m de haut" in _dfx and "plongée" in _dfx, "hauteur + inclinaison décrites"
    assert pr.describe_settings({"settings": {"on": False}}).startswith("ÉTEINT"), "éteint = n'éclaire pas"
    # Une TEINTE colorée REMPLACE la température (pas de « rouge » + « tungstène » contradictoires)
    _dt = pr.describe_settings({"family": "led_panel", "model": "ARRI SkyPanel S60-C",
                               "settings": {"on": True, "cct": 2800, "hue": 0, "saturation": 100}})
    assert "rouge" in _dt and "2800 K" not in _dt and "tungst" not in _dt.lower(), \
        "teinte colorée → pas de température contradictoire"
    # Libellé de couleur TRANCHÉ (jamais « rose/rouge »)
    assert "/" not in pr._hue_label(0) and pr._hue_label(0) == "rouge", "libellé couleur net et décisif"
    # Fenêtre de réglages adaptée aux capacités + menu clic droit + report prompt
    from ui.dialog_projector_settings import ProjectorSettingsDialog
    _ps = ProjectorSettingsDialog(light={"family": "led_panel", "model": "ARRI SkyPanel S60-C"})
    assert _ps._sl_cct is not None and _ps._sl_hue is not None, "full = température + teinte"
    assert _ps._sl_height is not None and _ps._sl_tilt is not None, "hauteur + inclinaison"
    assert _ps._fx_combo is not None and _ps._louver_cb is not None, "effet + louver (SkyPanel)"
    _pt = ProjectorSettingsDialog(light={"family": "fresnel", "model": "ARRI 650 (tungstène)"})
    assert _pt._sl_cct is None and _pt._gel_combo is not None, "tungstène = gélatine, CCT fixe"
    assert _pt._fx_combo is None, "pas d'effets sur un tungstène"
    _pfx = ProjectorSettingsDialog(light={"family": "led_panel", "model": "ARRI SkyPanel S60-C",
                                          "settings": {"effect": "candle"}})
    assert _pfx._sl_cct is not None and not _pfx._sl_cct.isEnabled(), "couleur désactivée si effet actif"
    _psrc0 = inspect.getsource(__import__("ui.page_staging", fromlist=["_"]))
    assert "_settings_light" in _psrc0 and "Réglages du projecteur" in _psrc0, "clic droit → Réglages du projecteur"
    assert "_toggle_light" in _psrc0 and "Éteindre le projecteur" in _psrc0, "clic droit → allumer/éteindre"
    assert "_on_camera_context" in _psrc0 and "_camera_height" in _psrc0, "clic droit caméra → hauteur"
    assert "camera_distance_m" in _psrc0, "déplacer la caméra écrit la distance (DIST.) dans le storyboard"
    _cvsrc = inspect.getsource(__import__("ui.staging_canvas", fromlist=["_"]))
    assert "camera_context" in _cvsrc and 'setOpacity(0.30)' in _cvsrc, "signal caméra + jeton éteint grisé"
    assert "describe_settings" in inspect.getsource(
        __import__("core.staging", fromlist=["_"]).lighting_summary), \
        "les réglages partent dans la section [PLAN DE FEU]"
    # Plan de feu RELATIF À L'AXE CAMÉRA + distances CHIFFRÉES (échelle RÉELLE du décor)
    import core.staging as _stg
    assert _stg.plan_span_m({}) == 10.0 and hasattr(_stg, "camera_distance_m"), "échelle réelle du plan"
    _sid = "harness_light_axis"
    _stg.save(_sid, {"camera": {"x": .5, "y": .15, "angle": 0.0},
                     "actors": [{"name": "Sujet", "x": .5, "y": .55}], "props": [],
                     "lights": [{"name": "Key", "type": "key", "family": "led_panel",
                                 "model": "ARRI SkyPanel S60-C", "x": .25, "y": .5,
                                 "settings": {"on": True, "intensity": 90, "cct": 5600}},
                                {"name": "Off", "type": "fill", "family": "cob",
                                 "model": "Aputure LS 600d Pro", "x": .75, "y": .5,
                                 "settings": {"on": False}}]})
    _lt_top = _stg.lighting_summary(_sid)
    assert "côté caméra" in _lt_top and "m de Sujet" in _lt_top, "direction caméra + distance chiffrée"
    assert "Key" in _lt_top and "Off" not in _lt_top, "projecteur éteint exclu du prompt"
    assert _stg.camera_distance_m(_stg.get(_sid)) > 0, "distance caméra dérivée de l'échelle réelle"
    _rec = _stg.get(_sid); _rec["camera"]["y"] = .9; _stg.save(_sid, _rec)
    _lt_bot = _stg.lighting_summary(_sid)
    import re as _re2
    def _camside(t):
        m = _re2.search(r"côté caméra (\w+)", t)
        return m.group(1) if m else "-"
    assert _camside(_lt_top) != _camside(_lt_bot), "le côté caméra s'inverse si la caméra change de côté"
    # Clic droit sur la liste → copier le plan de feu / la mise en scène d'un autre plan
    assert "_on_list_context" in _psrc0 and "_copy_staging_from" in _psrc0 and "_do_copy" in _psrc0, \
        "copier d'un autre plan (scènes similaires)"
    from ui.page_staging import PageLighting as _PL
    _stg.save("cp_src", {"camera": {"x": .5, "y": .2}, "actors": [{"name": "A", "x": .5, "y": .5}],
                         "props": [], "lights": [{"name": "K", "type": "key", "family": "led_panel",
                                                  "model": "ARRI SkyPanel S60-C", "x": .3, "y": .5,
                                                  "settings": {"on": True}}]})
    _stg.save("cp_dst", {"camera": {"x": .5, "y": .2}, "actors": [], "props": [], "lights": []})
    _pl = _PL()
    _pl._shots = [{"id": "cp_src", "number": 1}, {"id": "cp_dst", "number": 2, "seedance_prompt": ""}]
    _pl._shot = None
    _pl._do_copy(_pl._shots[0], _pl._shots[1])
    assert len(_stg.get("cp_dst")["lights"]) == 1 \
        and _stg.get("cp_dst")["lights"][0]["model"] == "ARRI SkyPanel S60-C", \
        "le plan de feu est copié vers le plan cible"

    # Sections de prompt (7 sections, libellés crochets+emoji) + strip du son
    import core.prompt_sections as ps
    import api.screenplay as s_screenplay
    full = ps.build(action="action X", staging="perso à gauche", ambiance="tendu",
                    decor="salle à manger", lighting="key SkyPanel à droite",
                    technique="plan moyen, caméra fixe", sound="pluie")
    for lbl in ("ACTION", "MISE EN SCÈNE", "AMBIANCE", "DÉCOR", "PLAN DE FEU", "TECHNIQUE", "SOUND DESIGN"):
        assert lbl in full, f"section {lbl} présente"
    assert "🎬" in full and "🎵" in full, "emojis dans les libellés de sections"
    assert "SOUND DESIGN" not in ps.strip_for_video(full), "son non envoyé à la vidéo"
    assert ps.parse(full)["action"] == "action X" and ps.parse(full)["technique"] == "plan moyen, caméra fixe"
    # Rétro-compatibilité : anciens libellés sans emoji toujours parsés
    legacy = "[ACTION]\nvieux\n\n[SOUND DESIGN]\nbruit"
    assert ps.parse(legacy)["action"] == "vieux" and ps.parse(legacy)["sound"] == "bruit"
    # Technique déterministe depuis les champs caméra
    tech = s_screenplay._technique_line({"shot_size": "PE", "camera_movement": "Travelling avant",
                                         "focal": "35mm", "optic": "Anamorphique", "speed": "Ralenti"})
    _tl = tech.lower()
    assert "plan d'ensemble" in _tl and "35mm" in _tl and "ralenti" in _tl and "anamorphique" in _tl, tech

    # api/real strippe la section son avant envoi Seedance
    rsrc = inspect.getsource(__import__("api.real", fromlist=["_"]))
    assert "strip_for_video" in rsrc, "real.py retire le bloc son"

    # Résumés mise en scène / plan de feu
    import core.staging as st
    assert hasattr(st, "staging_summary") and hasattr(st, "lighting_summary")
    # Sync staging → storyboard : placement acteurs SEUL + placement caméra (technique)
    assert hasattr(st, "staging_actors_summary") and hasattr(st, "camera_placement"), \
        "acteurs seuls (→ [MISE EN SCÈNE]) + caméra (→ champs techniques)"

    # Worker sync : options + assemblage des sections
    sw = inspect.getsource(__import__("api.screenplay", fromlist=["_"]))
    assert "sync_staging" in sw and "sync_lighting" in sw and "_finish" in sw

    # Dialog sync : 2 nouvelles cases
    dsrc = inspect.getsource(__import__("ui.dialog_storyboard_sync", fromlist=["_"]))
    assert "sync_staging" in dsrc and "sync_lighting" in dsrc

    # Canevas : rotation (poignée + modes) + clic droit
    cvsrc = inspect.getsource(__import__("ui.staging_canvas", fromlist=["_"]))
    assert "_RotKnob" in cvsrc and "set_tool" in cvsrc and "set_angle" in cvsrc
    assert "actor_context" in cvsrc and "light_context" in cvsrc
    assert "contextMenuEvent" in cvsrc

    # Page : Déplacer/Rotation/Générer-le-plan RETIRÉS (souris + poignée) ; nouveaux
    # sélecteur de plan, « Ajouter acteur » (casting complet) et menu Synchronisation.
    psrc = inspect.getsource(__import__("ui.page_staging", fromlist=["_"]))
    assert "_btn_move" not in psrc and "_btn_rotate" not in psrc, "boutons Déplacer/Rotation retirés"
    assert "_on_generate_plan" not in psrc and "_btn_gen" not in psrc, \
        "génération de plan retirée (→ Synchronisation)"
    assert "_plan_combo" in psrc and "plan_decor_id" in psrc, "sélecteur de plan de décor par plan"
    assert "Ajouter acteur" in psrc and "list_characters" in psrc, "Ajouter acteur = casting complet"
    assert "_btn_sync" in psrc and "_sync_decors" in psrc and "_sync_to_storyboard" in psrc, \
        "menu Synchronisation (décors ↔ storyboard, 2 sens)"
    # Boutons rotation (⟲ ⟳) + poubelle (🗑) RETIRÉS → souris/poignée + touche Suppr + clic droit
    assert "rotate_selected" not in psrc, "boutons de rotation retirés (souris/poignée)"
    assert "_sc_del" in psrc and "remove_model" in psrc, "Suppr + clic droit Supprimer"
    assert "_on_save_staging" in psrc and "_on_open_staging" in psrc and "staging_saves_dir" in psrc, \
        "Sauvegarder/Ouvrir (dossier dédié Mise en scène / Plan de feu)"
    assert "ProjectorDialog" in psrc and "_on_light_context" in psrc and "_on_actor_context" in psrc
    # Auto-synchro INSTANTANÉE (débouncée) des sections du prompt depuis le canevas —
    # plus besoin du menu Synchronisation pour le plan courant.
    assert "_apply_current_to_storyboard" in psrc and "_sync_timer" in psrc, \
        "auto-synchro instantanée des sections du prompt"
    assert "_sync_timer.start" in inspect.getsource(__import__("ui.page_staging", fromlist=["_"]).PageStaging._autosave), \
        "l'autosave déclenche la synchro débouncée"
    assert hasattr(ps, "technique_line"), "technique_line centralisée dans prompt_sections"
    # Découpage : la section [🖼️ TECHNIQUE] se reconstruit depuis les champs caméra à la sauvegarde du plan
    dsh = inspect.getsource(__import__("ui.dialog_shot", fromlist=["_"]).ShotDialog._on_save)
    assert "technique_line" in dsh, "découpage : Technique reconstruite depuis les champs caméra"
    # Édition INLINE focale/mouvement (etc.) dans le storyboard → [🖼️ TECHNIQUE] réécrite
    sbsrc = inspect.getsource(__import__("ui.page_storyboard", fromlist=["_"]))
    assert "_rebuild_technique" in sbsrc and "_CAM_FIELDS" in sbsrc, \
        "storyboard : changer focale/mouvement réécrit la section Technique inline"
    # Clic droit dans le storyboard → DUPLIQUER un plan (copie + mise en scène)
    assert "duplicate_requested" in sbsrc and "_on_duplicate" in sbsrc \
        and "Dupliquer le plan" in sbsrc, "clic droit storyboard → Dupliquer"
    import core.storyboard as _sb2
    assert hasattr(_sb2, "duplicate_shot"), "API duplicate_shot"
    _src = _sb2.save_shot({"scene_title": "Plan original", "seedance_prompt": "[🎬 ACTION]\nx"})
    _vid = _src.get("version_id")
    _before = len(_sb2.list_shots(_vid))
    _dup = _sb2.duplicate_shot(_src["id"])
    assert _dup and _dup["id"] != _src["id"], "un nouveau plan est créé"
    assert _dup.get("scene_title", "").endswith("(copie)"), "titre suffixé « (copie) »"
    assert "ACTION" in _dup.get("seedance_prompt", ""), "contenu (prompt) copié"
    assert len(_sb2.list_shots(_vid)) == _before + 1, "un plan de plus dans la version"
    # « Tout supprimer » retire AUSSI le plan de décor assigné (B4)
    from ui.staging_canvas import StagingCanvas as _SC2
    _cp = _SC2(mode="staging")
    _cp.load({"plan_image": "x.png", "camera": {"x": .5, "y": .8, "angle": 0.0},
              "actors": [], "props": [], "lights": []})
    assert _cp.has_clearable() is True, "un plan de fond compte comme « à supprimer »"
    _cp.clear_all()
    assert _cp._record.get("plan_image") == "" and _cp._record.get("plan_decor_id") == "__none__", \
        "Tout supprimer vide aussi le plan de décor (figé sur « aucun »)"
    # core.staging : export/import par fichier + résolution « aucun plan »
    assert hasattr(st, "export_staging_to") and hasattr(st, "import_staging_from") \
        and hasattr(st, "staging_saves_dir"), "save/open mise en scène par fichier"
    # Bouton ROUGE « Tout supprimer » à droite (Mise en scène ET Plan de feu, par héritage)
    assert "_btn_clear_all" in psrc and "Tout supprimer" in psrc and "clear_all" in psrc, \
        "bouton rouge Tout supprimer"
    # Régression : après « Tout supprimer », les acteurs ne sont PAS ré-amorcés au
    # rechargement (flag _actors_seeded) — sinon la suppression semblait sans effet.
    assert "_actors_seeded" in psrc, "acteurs amorcés une seule fois (pas de re-seed)"
    from ui.page_staging import PageStaging, PageLighting
    for _C in (PageStaging, PageLighting):
        _p = _C()
        assert hasattr(_p, "_btn_clear_all") and hasattr(_p, "_on_clear_all"), \
            f"{_C.__name__} : bouton Tout supprimer"
    # Le canevas vide réellement les éléments éditables + détecte le « rien à faire »
    assert "has_clearable" in psrc and "Rien à supprimer" in psrc, \
        "feedback quand il n'y a rien à supprimer"
    from ui.staging_canvas import StagingCanvas as _SC, _Token as _Tk
    _cc = _SC(mode="staging")
    _cc.load({"plan_image": "", "camera": {"x": .5, "y": .8, "angle": 0.0},
              "actors": [{"name": "X", "x": .3, "y": .5}], "props": [], "lights": []})
    assert _cc.has_clearable() is True, "détecte des éléments à supprimer"
    _cc.clear_all()
    assert _cc.has_clearable() is False, "plus rien à supprimer après clear_all"
    assert [it for it in _cc._scene.items() if isinstance(it, _Tk) and not it.reference and it.kind != "camera"] == [], \
        "clear_all vide les jetons éditables"


@test
def scenario_onglet_mise_en_page():
    """Page Scénario : 2 onglets (Scénario / Mise en page PANDORA) façon Live —
    la mise en page va dans son onglet et NE touche PAS au scénario."""
    from ui.page_scenario import PageScenario
    p = PageScenario()
    assert hasattr(p, "_editor_tabs") and hasattr(p, "_layout_view"), "onglets éditeur"
    assert p._editor_tabs.count() == 2, "Scénario + Mise en page PANDORA"
    assert not p._editor_tabs.isTabEnabled(1), "Mise en page grisée tant que vide"
    # La mise en page n'écrase pas le scénario
    p._set_editor_text("SCENARIO ORIGINAL")
    p._current = {}
    p._apply_layout("MISE EN PAGE PANDORA")
    assert p._editor_text.toPlainText().strip() == "SCENARIO ORIGINAL", "scénario intact"
    assert "MISE EN PAGE" in p._layout_view.toPlainText()
    # Même présentation que l'onglet Scénario : texte CENTRÉ (plus de colonne 900 px
    # collée à gauche). Les deux QTextEdit partagent l'alignement centré horizontal.
    from PyQt6.QtCore import Qt as _Qt
    _ed_align = p._editor_text.document().defaultTextOption().alignment()
    _lv_align = p._layout_view.document().defaultTextOption().alignment()
    assert bool(_ed_align & _Qt.AlignmentFlag.AlignHCenter), "onglet Scénario centré"
    assert bool(_lv_align & _Qt.AlignmentFlag.AlignHCenter), \
        "onglet Mise en page centré comme Scénario"
    assert p._editor_tabs.isTabEnabled(1) and p._editor_tabs.currentIndex() == 1
    assert p._current.get("layout_content"), "mise en page persistée séparément"
    # La fenêtre de mise en page applique vers l'onglet (pas _set_editor_text)
    fw = inspect.getsource(PageScenario._open_format_window)
    assert "_apply_layout" in fw and "_set_editor_text" not in fw, \
        "la fenêtre Mise en page écrit dans l'onglet dédié"
    # Plus de colonne fixe 900 px collée à gauche : pleine largeur centrée comme l'éditeur
    be = inspect.getsource(PageScenario._build_editor)
    assert "setFixedWidth(900)" not in be, "plus de colonne 900 px collée à gauche"
    assert "setDefaultTextOption(_opt)" in be, "même alignement centré que l'éditeur"


@test
def scenario_storyboard_save_open():
    """Sauvegarde / ouverture PHYSIQUE du scénario (dossier Scénario) et du
    storyboard (dossier Storyboard) — fichiers nommés dans le dossier du projet."""
    import core.scenario as sc, core.storyboard as sb
    # API présentes
    for m in ("export_scenario_file", "import_scenario_file", "list_saved"):
        assert hasattr(sc, m), f"scenario.{m}"
    for m in ("export_storyboard", "import_storyboard", "list_saved"):
        assert hasattr(sb, m), f"storyboard.{m}"
    # Page Scénario : boutons Sauvegarder/Ouvrir, plus de combo Versions
    from ui.page_scenario import PageScenario
    ps = PageScenario()
    assert hasattr(ps, "_btn_scn_save") and hasattr(ps, "_btn_scn_open"), "boutons scénario"
    assert not hasattr(ps, "_version_combo"), "contrôles Versions retirés"
    assert hasattr(ps, "_on_save_scenario_file") and hasattr(ps, "_on_open_scenario_file")
    # Page Storyboard : boutons Sauvegarder/Ouvrir près de Synchronisation
    from ui.page_storyboard import PageStoryboard
    pb = PageStoryboard()
    assert hasattr(pb, "_btn_save_sb_file") and hasattr(pb, "_btn_open_sb_file")
    assert hasattr(pb, "_on_save_storyboard_file") and hasattr(pb, "_on_open_storyboard_file")


@test
def transcode_h264_et_starlight2():
    """Transcodage H.264 auto des clips avant envoi moteur + modèles Starlight 2
    dans l'Upscaling Topaz (Astra absent de fal.ai)."""
    from core.video_utils import (ensure_engine_video, is_engine_compatible,
                                   video_needs_transcode)
    assert ensure_engine_video("absent.mxf") == "absent.mxf", "no-op si fichier absent"
    assert is_engine_compatible("absent.mxf") is False
    assert video_needs_transcode("absent.mxf") == "", "no-op si fichier absent"
    # Transcode PROGRESSIF + plafond 1080p (anti-trames sur vidéo progressive).
    import core.video_utils as vu
    vsrc = inspect.getsource(vu.ensure_engine_video)
    assert "yadif=deint=interlaced" in vsrc, "désentrelacement conditionnel (anti-trames)"
    assert "min(1080,ih)" in vsrc, "plafond 1080p (tous moteurs)"
    # api/real transcode le clip source avant l'upload
    import api.real as r
    assert "ensure_engine_video" in inspect.getsource(r), "transcodage H.264 avant upload"
    # Modifier des clips : message d'info AVANT conversion (conseil pré-export).
    de = inspect.getsource(__import__("ui.tab_davinci_edit", fromlist=["_"]))
    assert "video_needs_transcode" in de and "Conversion avant envoi" in de, \
        "message de conversion + conseil pré-export"
    # Upscaling : Starlight 2 présents, Astra absent
    import api.upscale as up
    vals = [v for _, v in up.TOPAZ_MODELS]
    assert "Starlight Precise 2" in vals and "Starlight Fast 2" in vals and "Gaia 2" in vals
    assert not any("Astra" in v for v in vals), "Astra non dispo sur fal.ai"


@test
def draw_to_video():
    """Draw-to-Video : dessin sur une image du clip → référence + prompt préfixé.
    Time code SMPTE (HH:MM:SS:FF) au lieu des secondes + ré-édition du dessin."""
    import tempfile
    from ui.dialog_draw_video import DrawVideoDialog, _DrawCanvas, _format_tc
    d = DrawVideoDialog("absent.mp4", tempfile.gettempdir())
    assert d._canvas.has_base(), "canevas avec image de fond (repli blanc si ffmpeg/clip absent)"

    # Time code SMPTE plutôt que des secondes
    assert _format_tc(0, 25.0) == "00:00:00:00"
    assert _format_tc(50, 25.0) == "00:00:02:00"               # 50 images @25 = 2 s
    assert _format_tc(3661 * 25 + 7, 25.0) == "01:01:01:07"
    tc = d._time_lbl.text()
    assert len(tc) == 11 and tc.count(":") == 3, "label = vrai time code HH:MM:SS:FF"
    init_src = inspect.getsource(DrawVideoDialog.__init__)
    assert "Time Code" in init_src and "Instant :" not in init_src, "libellé « Time Code »"

    # Ré-édition : paramètres prev_overlay/prev_frame + accesseurs + round-trip calque
    params = inspect.signature(DrawVideoDialog.__init__).parameters
    assert "prev_overlay" in params and "prev_frame" in params, "ré-ouverture éditable"
    assert hasattr(d, "overlay_path") and hasattr(d, "frame_index"), "accesseurs de ré-édition"
    ovp = os.path.join(tempfile.gettempdir(), "test_overlay_drawvideo.png")
    assert d._canvas.export_overlay(ovp) and os.path.isfile(ovp), "export du calque seul"
    d._canvas.set_overlay(ovp)   # rechargement d'un calque existant ne doit pas planter

    from ui.tab_davinci_edit import TabDavinciEdit
    t = TabDavinciEdit()
    assert hasattr(t, "_btn_draw") and hasattr(t, "_on_draw_to_video") and hasattr(t, "_draw_images")
    assert hasattr(t, "_draw_overlays") and hasattr(t, "_draw_frames"), "mémorisation pour ré-édition"
    # Dessiner accessible AUSSI depuis le prompt par-clip (pas seulement le global).
    assert hasattr(t, "_btn_draw_pc"), "bouton Dessiner présent dans le prompt par-clip"
    src = inspect.getsource(TabDavinciEdit)
    # L'image annotée n'est PAS envoyée comme référence (les traits seraient
    # reproduits) → passée comme GUIDE via draw_guidance_path ; Claude Vision côté
    # worker la lit pour réécrire le prompt sans les traits.
    assert "draw_guidance_path" in src, "image annotée passée comme guide (pas en référence)"
    assert "ref_images.append(_draw_img)" not in src, "les traits ne partent PAS à Seedance"
    rsrc = inspect.getsource(__import__("api.real", fromlist=["_"]))
    assert "_analyze_draw_guidance" in rsrc and "draw_guidance_path" in rsrc, \
        "Claude Vision décrit les zones marquées, traits jamais envoyés au modèle vidéo"
    assert "prev_overlay=" in src and "overlay_path()" in src and "frame_index()" in src, \
        "le clic rouvre le dessin existant (ré-édition)"
    # Bouton « Dessiner sur la vidéo » remplacé par son LOGO (icône, sans libellé)
    assert "draw_to_video.png" in src, "bouton = logo Dessiner sur la vidéo"
    assert t._btn_draw.text() == "" and not t._btn_draw.icon().isNull(), "bouton icône (logo)"
    # Logo placé à DROITE du rectangle de prompt (pas dans la rangée du carré de réf.)
    assert "_pg_prompt_row.addWidget(self._btn_draw" in src, "logo à droite du prompt"
    # File d'attente : bouton pleine largeur (stretch) aligné à gauche, plus rétréci
    assert "addWidget(self._btn_generate, 1)" in src, "bouton file d'attente pleine largeur"


@test
def nouveaux_moteurs_fal_2026():
    """Veille fal.ai (2026-06-21) intégrée : Lyria 3 Pro, Seedream 5/4.5 + Z-Image +
    Qwen-Image, Seedance 1.5 Pro / LTX-2 / Wan 2.7 / Hailuo 2.3, TTS MiniMax 2.8 /
    Gemini / Inworld / Qwen3 / Maya1, Foley Control."""
    import importlib, inspect, os, sys

    # — Musique : Lyria 3 Pro nouveau défaut —
    import api.music as mu
    assert mu.MUSIC_ENGINES["lyria3"]["endpoint"] == "fal-ai/lyria3/pro"
    assert mu.default_engine() == "lyria3" and mu.ENGINE_ORDER[0] == "lyria3"

    # — Image : Studio Images (Seedream 5/4.5, Z-Image, Qwen-Image) —
    _sd = os.path.join(os.path.dirname(os.path.dirname(__file__)), "studio_images")
    if _sd not in sys.path:
        sys.path.insert(0, _sd)
    eng = importlib.import_module("engines")
    for k in ("seedream5", "seedream45", "zimage", "qwen_image"):
        assert k in eng.ENGINES, f"moteur image {k} manquant"
    ep, _a, _ = eng.build_request("seedream5", "x", (1024, 768), "1K", [])
    assert ep == "fal-ai/bytedance/seedream/v5/lite/text-to-image"
    ep2, a2, _ = eng.build_request("seedream5", "x", (1024, 768), "1K", ["data:img"])
    assert ep2.endswith("/edit") and "image_urls" in a2, "Seedream 5 édition (refs)"

    # — Vidéo : workers + endpoints exacts —
    import api.video_engines as ve
    assert ve.Seedance15Worker.ENDPOINT_T2V == "fal-ai/bytedance/seedance/v1.5/pro/text-to-video"
    assert ve.Seedance15Worker.ENDPOINT_I2V.endswith("/image-to-video") and ve.Seedance15Worker.END_FRAME
    assert ve.LTX2Worker.ENDPOINT_T2V == "fal-ai/ltx-2/text-to-video"
    assert ve.Wan27Worker.ENDPOINT_T2V == "fal-ai/wan/v2.7/text-to-video"
    assert ve.Hailuo23Worker.ENDPOINT_T2V == "fal-ai/minimax/hailuo-2.3/pro/text-to-video"

    # — Onglet vidéo direct : 6 nouveaux moteurs + dispatch (Cinéma ET Live) —
    for mod in ("ui.tab_video_engines", "ui.tab_video_engines_live"):
        m = importlib.import_module(mod)
        keys = [k for _, k, _ in m.TabVideoEngines._ENGINES]
        for need in ("seedance15_t2v", "seedance15_i2v", "ltx2_t2v", "ltx2_i2v",
                     "wan27_t2v", "hailuo23_t2v"):
            assert need in keys, f"{mod}: moteur {need} manquant"
        dsrc = inspect.getsource(m.TabVideoEngines._on_generate)
        for w in ("Seedance15Worker", "LTX2Worker", "Wan27Worker", "Hailuo23Worker"):
            assert w in dsrc, f"{mod}: dispatch {w} manquant"

    # — TTS : registre + workers + page Doublage (3e mode + moteur de clonage) —
    import api.tts as tts
    assert len(tts.SPEECH_ENGINES) == 6 and "minimax-2.8-hd" in tts.SPEECH_ENGINES
    assert hasattr(tts, "FalSpeechWorker") and hasattr(tts, "FoleyControlWorker")
    psrc = inspect.getsource(importlib.import_module("ui.page_doublage"))
    for tok in ("_speech_combo", "_clone_engine_combo", "FalSpeechWorker", "IndexTTS2Worker"):
        assert tok in psrc, f"page_doublage : {tok} manquant"

    # — Foley Control câblé dans les deux Sound Design —
    for mod in ("ui.tab_sound_design", "ui.tab_sound_design_live"):
        s = inspect.getsource(importlib.import_module(mod))
        assert "FoleyControlWorker" in s and "_video_engine_combo" in s, f"{mod}: Foley non câblé"


@test
def version_beta_et_update_check():
    """Une VERSION suffixée « -bêta » ne doit ni faire croire l'app périmée
    (parse robuste → numérique) ni crasher la bannière (disconnect gardé contre
    TypeError, l'exception réellement levée par PyQt6 sur un signal non connecté)."""
    import inspect
    from api.update_check import _parse_version
    import core.version as ver
    assert _parse_version("1.2.0-bêta") == (1, 2, 0)
    assert _parse_version("v1.2.0") == (1, 2, 0)
    assert _parse_version("1.2.0-bêta") == _parse_version("1.2.0"), "bêta ≠ périmé"
    assert _parse_version(ver.VERSION) and _parse_version(ver.VERSION)[0] >= 1, \
        "VERSION du build doit parser en numérique (pas (0,))"
    src = inspect.getsource(__import__("ui.pandora_window", fromlist=["_"]))
    i = src.find("_update_dl_btn.clicked.disconnect()")
    assert i != -1 and "TypeError" in src[i - 200:i + 200], \
        "disconnect() de la bannière doit attraper TypeError"


@test
def sound_design_cinema_file_plans():
    """Sound Design Cinéma : sélection de plans → file d'attente (porté du Live).
    Sonorise chaque plan via sa section [🎵 SOUND DESIGN] (sound_prompt) ;
    plans sans prompt ignorés ; assemblage bande-son calée optionnel."""
    import inspect
    from ui.tab_sound_design import TabSoundDesign
    t = TabSoundDesign()
    for attr in ("_storyboard", "_btn_load_plans", "_btn_cancel_queue", "_auto_mix_cb"):
        assert hasattr(t, attr), f"Sound Design : {attr} manquant"
    assert type(t._storyboard).__name__ == "StoryboardSelector"
    # File triée par numéro de plan ; plans sans prompt son ignorés.
    t._build_queue_from_shots([
        {"number": 2, "scene_title": "B", "sound_prompt": "rain", "duration": 4},
        {"number": 1, "scene_title": "A", "sound_prompt": "wind", "duration": 6},
        {"number": 3, "scene_title": "C", "sound_prompt": "",     "duration": 5},
    ])
    assert [q["number"] for q in t._sfx_queue] == [1, 2], t._sfx_queue
    # Commandes ffmpeg pures (conformation + assemblage durée exacte).
    assert "atrim=0:4" in " ".join(TabSoundDesign._build_conform_cmd("ffmpeg", "a", "b", 4.0))
    assert "concat=n=2" in " ".join(
        TabSoundDesign._build_assemble_cmd("ffmpeg", ["a", "b"], [4.0, 6.0], "o"))
    # Le conteneur rafraîchit le conducteur au changement d'onglet.
    sw = inspect.getsource(__import__("ui.seedance_widget", fromlist=["_"]))
    assert "self.tab_sound.refresh()" in sw, "refresh du conducteur non câblé"


@test
def assistant_ia_routage_par_tache():
    """Profil par DÉFAUT = routage IDÉAL par tâche (le moins de crédits, pas d'IA
    surdimensionnée) : Opus 4.8 UNIQUEMENT pour le storyboard, Sonnet pour
    scénario/sync, Haiku pour le reste. Un choix global explicite s'applique partout ;
    un override par tâche prime sur tout."""
    import core.config as _cfg
    import core.ai_provider as ap
    _orig = _cfg.load_config

    def _mf(task, tier, conf):
        _cfg.load_config = lambda: conf
        p, m = ap._resolve_engine(task)
        return ap._model(tier, p, m)

    try:
        d = {"ai_provider": "anthropic", "ai_model_creative": "claude-opus-4-8",
             "ai_task_engines": {}}
        assert _mf("storyboard_gen", "creative", d) == "claude-opus-4-8", "storyboard = Opus"
        assert _mf("extraction", "creative", d) == "claude-haiku-4-5", "extraction = Haiku"
        assert _mf("screenplay", "creative", d) == "claude-sonnet-4-6", "scénario = Sonnet"
        assert _mf("sync", "creative", d) == "claude-sonnet-4-6", "sync = Sonnet"
        assert _mf("translate", "utility", d) == "claude-haiku-4-5", "traduction = Haiku"
        # Config vide → même routage intelligent.
        assert _mf("storyboard_gen", "creative", {}) == "claude-opus-4-8"
        assert _mf("extraction", "creative", {}) == "claude-haiku-4-5"
        # Global explicite → s'applique partout (Sonnet pour TOUTES les tâches).
        g = {"ai_provider": "anthropic", "ai_model_creative": "claude-sonnet-4-6"}
        assert _mf("storyboard_gen", "creative", g) == "claude-sonnet-4-6"
        assert _mf("extraction", "creative", g) == "claude-sonnet-4-6"
        # Override par tâche prioritaire.
        o = {"ai_provider": "anthropic", "ai_model_creative": "claude-opus-4-8",
             "ai_task_engines": {"storyboard_gen": "haiku"}}
        assert _mf("storyboard_gen", "creative", o) == "claude-haiku-4-5"
        # Paramètres : le combo présélectionne le profil optimisé (défaut).
        _cfg.load_config = lambda: {}
        from ui.page_settings import SettingsPage
        ps = SettingsPage()
        assert ps.ai_combo.currentData() == ("anthropic", "claude-opus-4-8"), \
            f"défaut attendu = profil optimisé, eu {ps.ai_combo.currentData()}"
    finally:
        _cfg.load_config = _orig


@test
def mise_en_scene_placement_precis():
    """Placement des personnages RELATIF aux éléments du décor (« à droite de la
    table »), vu de la caméra (bascule si on bouge l'acteur OU la caméra) ;
    + ambiance lumière calquée sur le type de projecteur (en plus du technique)."""
    import inspect
    import core.staging as st
    import core.projectors as pr
    # Sans caméra : table au centre, acteur à gauche puis à droite → bascule.
    rec = {"actors": [{"name": "M", "x": 0.30, "y": 0.50}],
           "props": [{"name": "la table", "x": 0.50, "y": 0.50}]}
    assert "à gauche de la table" in st._actor_placement_phrase(rec, rec["actors"][0])
    rec["actors"][0]["x"] = 0.70
    assert "à droite de la table" in st._actor_placement_phrase(rec, rec["actors"][0])
    rec["actors"][0].update(x=0.50, y=0.50)
    assert st._actor_placement_phrase(rec, rec["actors"][0]) == "à la table"
    # Caméra : le côté est relatif à l'axe caméra (2 persos de part et d'autre).
    rec3 = {"camera": {"x": 0.5, "y": 0.95},
            "actors": [{"name": "M", "x": 0.3, "y": 0.5}, {"name": "J", "x": 0.7, "y": 0.5}],
            "props": [{"name": "la table", "x": 0.5, "y": 0.5}]}
    a = st._actor_placement_phrase(rec3, rec3["actors"][0])
    b = st._actor_placement_phrase(rec3, rec3["actors"][1])
    assert "table" in a and "table" in b and a != b, (a, b)
    # Ambiance lumière : chaud (panneau doux) vs coloré (tube), calqué sur le type.
    warm = pr.ambiance_phrase({"family": "led_panel", "settings": {"on": True, "cct": 3200}})
    assert "chaude" in warm and "douce" in warm, warm
    col = pr.ambiance_phrase({"family": "tube", "settings": {"on": True, "saturation": 80, "hue": 255}})
    assert "colorée" in col, col
    # Le plan de feu injecte l'ambiance.
    assert "ambiance_phrase" in inspect.getsource(st.lighting_summary)
    # Analyse VISION du plan par Claude (placement précis vs mobilier visible),
    # auto-débouncée — pas d'ajout d'accessoires.
    ps = inspect.getsource(__import__("ui.page_staging", fromlist=["_"]))
    assert "_run_vision" in ps and "StagingVisionWorker" in ps and "_vision_timer" in ps, \
        "analyse vision du plan câblée en auto"
    from api.staging_vision import _positions_text
    pos = _positions_text([{"kind": "actor", "label": "Magalie", "x": 0.3, "y": 0.5},
                           {"kind": "camera", "x": 0.5, "y": 0.95, "info": "axe Face"}])
    assert "Magalie" in pos and "Caméra" in pos and "%" in pos, pos
    # Clic droit sur le VIDE du canevas → ajout au point cliqué (acteur/caméra ;
    # projecteur en Plan de feu).
    sc = inspect.getsource(__import__("ui.staging_canvas", fromlist=["_"]))
    assert "empty_context" in sc and "def place_camera" in sc, "clic droit vide + place_camera"
    assert "_on_empty_context" in ps and "Créer un projecteur" in ps, "menu clic droit d'ajout câblé"


@test
def placement_auto_hauteur_et_doublage():
    """3 finalisations : (1) mise en scène INITIALE auto à la génération (acteurs +
    caméra selon l'axe) ; (2) hauteur caméra à côté de la distance (storyboard) ;
    (3) Doublage depuis le storyboard (sélection de plans → dialogues extraits)."""
    import inspect
    import core.staging as st
    import core.storyboard as sb
    # (1) Semis acteurs + caméra depuis l'axe du plan.
    rec = st.seed_record_for_shot({"character_names": ["Magalie", "Jean"],
                                   "camera_axis": "Dos", "camera_height": "1,7 m"})
    assert len(rec["actors"]) == 2 and rec["camera"]["angle"] == 180.0
    assert rec["camera"].get("height") == 1.7, "hauteur reprise du plan"
    assert st.seed_record_for_shot({"camera_axis": "Face"})["camera"]["angle"] == 0.0
    assert st.ensure_seeded([]) == 0 and st.ensure_seeded([{"number": 1}]) == 0
    # Branché à la génération du storyboard (les 2 flux) + repli à l'ouverture.
    sc = inspect.getsource(__import__("ui.page_scenario", fromlist=["_"]))
    assert sc.count("ensure_seeded") >= 2, "semis câblé aux 2 flux de génération"
    pst = inspect.getsource(__import__("ui.page_staging", fromlist=["_"]))
    assert "seed_record_for_shot" in pst, "repli semis à l'ouverture (caméra incluse)"
    # (2) Hauteur caméra dans le storyboard (dialog + écriture depuis la mise en scène).
    ds = inspect.getsource(__import__("ui.dialog_shot", fromlist=["_"]))
    assert "_camera_height" in ds and "camera_height" in ds, "champ hauteur caméra"
    assert "camera_height" in pst, "hauteur écrite depuis la Mise en scène"
    # (3) Doublage depuis le storyboard.
    assert sb.extract_dialogues('Elle dit « Bonjour » et “Salut”.') == ["Bonjour", "Salut"]
    assert sb.extract_dialogues("rien") == []
    pd = inspect.getsource(__import__("ui.page_doublage", fromlist=["_"]))
    assert ("StoryboardSelector" in pd and "_load_dialogues" in pd
            and "extract_dialogues" in pd), "Doublage : sélection plans → dialogues"


@test
def decors_sept_vues_groupees():
    """7 vues d'une pièce → 7 DÉCORS distincts marqués `room_group`, regroupés en
    bandeaux dépliables (page Décors) ; plan d'architecte dédupliqué par pièce."""
    import inspect
    import core.decors as dec
    # Regroupement par pièce : ordre conservé, décors libres réunis sous "".
    g = dec.group_by_room([
        {"id": "1", "name": "Salon"},
        {"id": "2", "name": "SAM", "room_group": "SAM"},
        {"id": "3", "name": "SAM · Avant", "room_group": "SAM"},
    ])
    assert [k for k, _ in g] == ["", "SAM"] and len(g[1][1]) == 2
    cd = inspect.getsource(dec)
    assert 'setdefault("room_group"' in cd, "champ room_group au schéma"
    assert 'setdefault("room_view"' in cd, "champ room_view (face) au schéma"
    # Génération : les 2 flux créent des décors frères (room_group + face room_view).
    sg = inspect.getsource(__import__("ui.dialog_extract_generate", fromlist=["_"]))
    assert "room_group" in sg and "room_view" in sg and "_on_room_views_done" in sg
    dd = inspect.getsource(__import__("ui.dialog_decor", fromlist=["_"]))
    assert "room_group" in dd and "room_view" in dd and "_on_room_decors_done" in dd
    # UI : bandeaux dépliables + plan dédupliqué par pièce + badge de FACE (room_view).
    pd = inspect.getsource(__import__("ui.page_decors", fromlist=["_"]))
    assert ("_group_section" in pd and "group_by_room" in pd
            and "_fp_representatives" in pd and "_collapsed" in pd), "regroupement UI"
    assert "room_view" in pd, "badge de face (Avant/Arrière/…) sur la carte décor"


@test
def image_ia_chat_a_droite():
    """Onglet Image IA (panneau Studio Images partagé) : le chat Claude est à
    DROITE, comme le Storyboard — génération à gauche, puis panneau chat, puis
    poignée au bord droit ; flèche « ❮ » ouvert / « ❯ » fermé (identique au
    StoryboardChatToggleStrip). Fige le sens après les allers-retours passés."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "studio_images", "window.py"), encoding="utf-8") as f:
        src = f.read()
    i_gen    = src.find("body.addWidget(left_scroll, 1)")
    i_panel  = src.find("body.addWidget(self._chat_panel)")
    i_toggle = src.find("body.addWidget(self._chat_toggle)")
    assert -1 < i_gen < i_panel < i_toggle, \
        "Image IA : génération à gauche, puis chat + poignée à droite (comme Storyboard)"
    assert 'return "❮" if self._open else "❯"' in src, "flèche identique au chat Storyboard"
    # Référence : le Storyboard utilise bien la même convention de flèche.
    with open(os.path.join(root, "ui", "storyboard_chat.py"), encoding="utf-8") as f:
        assert 'return "❮" if self._open else "❯"' in f.read()


@test
def panneaux_guide_et_ia():
    """Panneaux latéraux : GAUCHE = « Guide » (pédagogie / guide d'utilisation),
    DROITE = « IA » (actions qui modifient le projet). Storyboard + Image IA +
    Live (alias) cohérents ; i18n EN « IA » → « AI »."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _src(rel):
        with open(os.path.join(root, rel), encoding="utf-8") as f:
            return f.read()

    # GAUCHE = Guide (en-tête + poignée), plus « Assistant » / poignée « IA ».
    ap = _src(os.path.join("ui", "assistant_panel.py"))
    assert 'self._title_lbl = QLabel("Guide")' in ap, "en-tête gauche = Guide"
    assert 'self._ia_lbl = QLabel("GUIDE")' in ap, "poignée gauche = GUIDE"
    # Bouton double Guide / IA : en mode IA le guide est masqué (pas tronqué) et
    # remplacé par un texte d'intro.
    assert ("_btn_mode_guide" in ap and "_btn_mode_ia" in ap and "_set_mode" in ap
            and "_ia_intro" in ap), "bouton double Guide/IA + intro IA"
    # Live = simple alias de la classe Cinéma (un seul source à renommer).
    al = _src(os.path.join("ui", "assistant_panel_live.py"))
    assert "from ui.assistant_panel import AssistantPanel" in al, "Live = alias (pas de doublon)"
    # DROITE = IA (en-tête + poignée) côté Storyboard, plus « CHAT » / « Chat Storyboard ».
    sc = _src(os.path.join("ui", "storyboard_chat.py"))
    assert 'translate("IA")' in sc and 'self._lbl = QLabel("IA")' in sc
    assert 'QLabel("CHAT")' not in sc, "plus de poignée « CHAT » au Storyboard"
    # DROITE = IA côté Image IA (panneau studio_images partagé).
    wi = _src(os.path.join("studio_images", "window.py"))
    assert 'self._lbl = QLabel("IA")' in wi and '_ttl = QLabel("IA")' in wi
    assert 'QLabel("CHAT")' not in wi, "plus de poignée « CHAT » côté Image IA"
    # i18n EN.
    import core.i18n as i18n
    assert i18n._FR_TO_EN.get("IA") == "AI"


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
