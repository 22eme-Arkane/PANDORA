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

# ── GARDE-FOU config (incident 2026-07-02) : les pages Paramètres sauvent
#    AUTOMATIQUEMENT au moindre changement de champ/combo → un test qui manipule
#    un combo écrirait la VRAIE data/config.json (clés API réelles, gitignorée
#    donc non restaurable). save_config est neutralisé pour TOUTE la session de
#    test, y compris les copies liées au niveau module (page_settings,
#    tab_settings). Un test qui veut vérifier une écriture doit monkeypatcher
#    localement vers un fichier temporaire.
import core.config as _cfg_mod
_cfg_mod.save_config = lambda cfg: None
for _mod_name in ("ui.page_settings", "ui.tab_settings"):
    try:
        _m = __import__(_mod_name, fromlist=["save_config"])
        _m.save_config = _cfg_mod.save_config
    except Exception:
        pass

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
    assert n == 10, "10 choix (PANDORA optimisé défaut, Sonnet, Haiku, Fable 5, GPT-5.5, Mistral, Kimi K2.7, GLM 4.7, Ollama, Personnalisé)"
    labels = [p.ai_combo.itemText(i) for i in range(n)]
    assert "optimisé" in labels[0] and "défaut" in labels[0], "PANDORA optimisé = défaut (1er)"
    assert any("Fable 5" in x for x in labels), "Fable 5 proposé"
    assert any("GPT-5.5" in x for x in labels), "GPT-5.5 proposé"
    assert any("Choix personnalisé" in x for x in labels), "Choix personnalisé proposé"
    assert any("PANDORA optimisé" in x for x in labels), "PANDORA optimisé proposé"
    assert any("Mistral" in x for x in labels) and any("Ollama" in x for x in labels)
    assert any("Kimi" in x for x in labels), "Kimi K2.7 proposé"
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
    """Build v1.3.0 DOUBLE ÉDITION : le .spec n'exclut PLUS le Live (décision
    2026-07-02) ; le mécanisme is_cinema_only reste (détection dynamique) et
    main.py garde sa branche conditionnelle pour un éventuel build Cinéma seul."""
    import core.edition as ed
    # En dev (live_window présent), l'édition complète est active → chooser
    assert ed.is_cinema_only() is False, "dev = édition complète (Live présent)"
    # main.py : démarrage conditionnel conservé (robustesse si Live absent)
    src_main = open("main.py", encoding="utf-8").read()
    assert "from core.edition import is_cinema_only" in src_main
    assert "if _CINEMA_ONLY:" in src_main, "branche Cinéma directe conservée"
    assert 'mode == "live" and not _CINEMA_ONLY' in src_main
    # Splash : bouton Retour optionnel (affiché en double édition)
    from PyQt6.QtWidgets import QApplication
    from ui.splash import SplashWindow
    assert "show_back" in inspect.getsource(SplashWindow.__init__)
    SplashWindow("cinema", show_back=False)   # ne doit pas lever
    # Le .spec n'exclut AUCUN module Live (double édition) + BUNDLE mac présent
    spec = open("pandora.spec", encoding="utf-8").read()
    exc = spec.split("excludes=[")[1].split("]")[0]
    for mod in ("live_window", "ui.chooser", "resolume", "core.live_mapping",
                "api.resolume_push", "ui.tab_t2v_live"):
        assert f'"{mod}"' not in exc, f".spec ne doit PLUS exclure {mod} (v1.3.0)"
    assert "BUNDLE(" in spec and "PANDORA.app" in spec, "cible macOS présente"
    # Version bumpée — build 1.3.4 (Cinéma + Live, Windows + macOS).
    from core.version import VERSION
    assert VERSION.split("-")[0] == "1.3.4", f"version attendue 1.3.4[-suffixe], lue {VERSION}"


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
def double_ecran_deuxieme_fenetre():
    """P5 — 2ᵉ fenêtre PANDORA (2 écrans) : bouton dans Paramètres (section
    Apparence, près du thème), méthode open_secondary_window sur la fenêtre,
    fenêtre secondaire qui saute l'onboarding et se ferme sans quitter l'app."""
    import ui.pandora_window as PW
    # 1) API de la fenêtre : param is_secondary + méthode d'ouverture
    src_init = inspect.getsource(PW.PandoraWindow.__init__)
    assert "is_secondary" in src_init, "PandoraWindow accepte is_secondary"
    assert "if not self._is_secondary" in src_init, "onboarding sauté en secondaire"
    assert hasattr(PW.PandoraWindow, "open_secondary_window"), "méthode d'ouverture"
    src_open = inspect.getsource(PW.PandoraWindow.open_secondary_window)
    assert "is_secondary=True" in src_open and "screens()" in src_open, \
        "ouvre une 2ᵉ fenêtre placée sur le 2ᵉ écran"
    assert "NonModal" in src_open, "2ᵉ fenêtre explicitement non modale (anti-bip/blocage)"
    # Rafraîchissement au retour de focus (données partagées entre les 2 fenêtres)
    assert hasattr(PW.PandoraWindow, "changeEvent") and hasattr(PW.PandoraWindow, "_refresh_on_focus")
    src_ce = inspect.getsource(PW.PandoraWindow.changeEvent)
    assert "ActivationChange" in src_ce and "_refresh_on_focus" in src_ce, \
        "recharge la page visible quand la fenêtre reprend le focus"
    assert "_current_nav" in inspect.getsource(PW.PandoraWindow._navigate), \
        "page courante mémorisée pour le rafraîchissement"
    # 2) La fermeture de la secondaire NE propose PAS de quitter le programme
    src_close = inspect.getsource(PW.PandoraWindow.closeEvent)
    assert "_is_secondary" in src_close and "e.accept()" in src_close, \
        "la 2ᵉ fenêtre se ferme sans dialogue de sortie"
    # 3) Le bouton d'activation est dans Paramètres (même section que le thème)
    from ui.page_settings import SettingsPage
    ps = SettingsPage()
    assert hasattr(ps, "_btn_second_window"), "bouton 2ᵉ fenêtre dans Paramètres"
    assert hasattr(ps, "_open_second_window"), "handler d'ouverture dans Paramètres"


@test
def pitch_deck_export_l2():
    """L2 — export d'un dossier de présentation (deck HTML autonome) depuis le
    storyboard : module PUR build_pitch_deck_html + bouton/handler dans la page."""
    import core.pitch_deck as pd
    shots = [
        {"number": 1, "scene_title": "Ouverture", "seq_name": "ACTE 1",
         "decor_name": "Rue", "character_names": ["Marc"], "duration": 6},
        {"number": 2, "scene_title": "Rencontre", "seq_name": "ACTE 1",
         "decor_name": "Café", "character_names": ["Marc", "Léa"], "duration": 8},
    ]
    chars  = [{"name": "Marc", "role": "Héros"}, {"name": "Léa", "role": ""}]
    decors = [{"name": "Rue"}, {"name": "Café"}]
    html_fr = pd.build_pitch_deck_html({"name": "Mon Film"}, shots, chars, decors, lang="fr")
    assert "Mon Film" in html_fr and "Dossier de présentation" in html_fr
    assert "Casting" in html_fr and "Décors" in html_fr and "Découpage" in html_fr
    assert "P1" in html_fr and "P2" in html_fr and "ACTE 1" in html_fr
    html_en = pd.build_pitch_deck_html({"name": "My Film"}, shots, chars, decors, lang="en")
    assert "Pitch deck" in html_en and "Cast" in html_en and "Shot breakdown" in html_en
    # Écriture réelle dans le dossier TEMPORAIRE du harnais (jamais la vraie config)
    out = os.path.join(_TMP, "deck.html")
    pd.export_pitch_deck(out, project={"name": "T"}, shots=shots,
                         characters=chars, decors=decors, lang="fr")
    assert os.path.isfile(out) and os.path.getsize(out) > 500
    # Export PDF (QPdfWriter) + images PNG (QImage) — rendu Qt natif, sans dep externe
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    pdf = pd.export_pitch_deck_pdf(os.path.join(_TMP, "deck.pdf"),
                                   project={"name": "T"}, shots=shots,
                                   characters=chars, decors=decors, lang="fr")
    assert os.path.isfile(pdf) and os.path.getsize(pdf) > 1000, "PDF non généré"
    imgs = pd.export_pitch_deck_images(os.path.join(_TMP, "deck"),
                                       project={"name": "T"}, shots=shots,
                                       characters=chars, decors=decors, lang="fr")
    assert len(imgs) >= 3 and all(os.path.isfile(p) for p in imgs), "PNG non générés"
    from ui.page_storyboard import PageStoryboard as _PS
    assert hasattr(_PS, "_on_export_pitch_deck"), "handler export dans la page"
    assert "_btn_pitch_deck" in inspect.getsource(_PS._build_shots_toolbar), \
        "bouton Pitch deck dans la barre d'outils du storyboard"


@test
def retake_cible_l4():
    """L4 — reprise ciblée « Retake » : modèle de prompt dédié dans « Modifier un
    clip » (reprend @Video1 à l'identique, corrige UNIQUEMENT le défaut décrit) +
    option dans le sélecteur « Type de modification »."""
    import ui.tab_davinci_edit as M
    assert "retake" in M._MOD_TEMPLATES, "modèle Retake absent de _MOD_TEMPLATES"
    tpl = M._MOD_TEMPLATES["retake"]
    assert "@Video1" in tpl and "UNIQUEMENT" in tpl, \
        "Retake : reprend @Video1 + corrige seulement le défaut"
    assert '"retake"' in inspect.getsource(M.TabDavinciEdit._build_ui), \
        "option Retake absente du sélecteur « Type de modification »"


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
    # P2 — respecter le nb de plans (un par beat) + JAMAIS de fusion silencieuse
    assert "{MERGE_POLICY}" in t and '"merged"' in t, "P2 : champ merged + placeholder strict"
    assert "beat" in t.lower() and "FUSION INTERDITE EN SILENCE" in t, \
        "P2 : un plan par beat + fusion déclarée"
    assert "strict_no_merge" in inspect.signature(s.GenerateStoryboardWorker.__init__).parameters, \
        "P2 : worker accepte strict_no_merge"
    assert "MODE STRICT" in s._storyboard_prompt("fr", True), "P2 : mode strict actif"
    assert "MODE STRICT" not in s._storyboard_prompt("fr", False), "P2 : normal sans mode strict"
    from ui.dialog_storyboard_generate import StoryboardGenerateDialog as _SGD
    for _m in ("_ask_merge_decision", "_reset_for_retry"):
        assert hasattr(_SGD, _m), f"P2 : dialogue {_m}"
    assert "strict_no_merge=True" in inspect.getsource(_SGD._on_done), \
        "P2 : « Séparer » relance en mode strict"
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
def rapports_supabase_table_seule():
    """Envoi d'avis/bugs/crashs vers Supabase (2026-07-13, « table seule ») : backend
    pur DÉSACTIVÉ tant que l'URL/clé ne sont pas renseignées (aucune requête), payload
    borné, worker done/failed, formulaire Contact présent SSI configuré, bouton
    « Envoyer le rapport » branché dans l'excepthook de crash."""
    import core.support_backend as sb
    # Payload : bornes + contexte (version/OS) — pur, aucune requête réseau.
    p = sb.build_payload("bug", "m" * 20000, "e" * 500, "l" * 50000)
    assert len(p["message"]) == sb._MAX_MESSAGE and len(p["email"]) == sb._MAX_EMAIL
    assert len(p["log"]) == sb._MAX_LOG, "le log doit garder sa FIN, borné"
    from core.version import VERSION
    assert p["app_version"] == VERSION and p["kind"] == "bug" and p["os"]
    assert sb.build_payload("inconnu", "x")["kind"] == "avis", "kind inconnu → avis"
    # Non configuré → submit_report REFUSE (jamais de requête vers une URL vide).
    if not sb.is_configured():
        try:
            sb.submit_report("avis", "test")
            assert False, "submit_report doit refuser sans configuration"
        except RuntimeError:
            pass
    # Worker : signaux done/failed (jamais « finished » — doctrine projet).
    from api.report import SendReportWorker
    w = SendReportWorker("avis", "x")
    assert hasattr(w, "done") and hasattr(w, "failed") and "finished" not in (
        n for n in ("done", "failed"))
    # Fenêtre Contact : formulaire construit SEULEMENT si configuré (repli e-mail sinon).
    from ui.dialog_contact import ContactDialog
    src = inspect.getsource(ContactDialog)
    assert "_build_report_form" in src and "is_configured" in src
    dlg = ContactDialog(None)
    assert hasattr(dlg, "_report_msg") == sb.is_configured(), \
        "formulaire présent ssi serveur configuré"
    # Crash : bouton « Envoyer le rapport » dans l'excepthook (appel bloquant court).
    import main as _main
    _hsrc = inspect.getsource(_main._install_excepthook)
    assert "submit_report" in _hsrc and "Envoyer le rapport" in _hsrc \
        and "is_configured" in _hsrc, "excepthook : envoi du rapport de crash absent"


@test
def refs_visuelles_persistance_bibliotheque_chat_cinema():
    """Portage Live→Cinéma 2026-07-13 : refs visuelles persistées avec le scénario,
    bouton Analyser qui ROUVRE l'analyse existante, bibliothèque d'analyses
    inter-projets, chat direction artistique dans la fenêtre, DA injectée dans
    l'application des suggestions et la session de co-écriture."""
    from ui.page_scenario import PageScenario
    # 1. Persistance projet : refs + analyse écrites et restaurées avec le scénario
    src_save = inspect.getsource(PageScenario._save)
    assert "ref_images" in src_save and "ref_analysis" in src_save and "ref_enriched" in src_save, \
        "refs + analyse sauvegardées avec le scénario"
    src_open = inspect.getsource(PageScenario._open_scenario)
    assert "ref_images" in src_open and "ref_analysis" in src_open, \
        "refs + analyse restaurées à l'ouverture du projet"
    # 2. Le bouton Analyser rouvre l'analyse existante (pas de relance silencieuse)
    src_an = inspect.getsource(PageScenario._on_analyze_refs)
    assert "_open_refs_window" in src_an and "_start_refs_analysis" in src_an, \
        "analyse existante rouverte ; relance via _start_refs_analysis"
    # 3. Fenêtre : Relancer / Nouvelle / Sauvegarder / Bibliothèque / chat DA + persistance
    src_w = inspect.getsource(PageScenario._open_refs_window)
    for token in ("Relancer l'analyse", "Nouvelle analyse", "ref_library", "RefsChatWorker",
                  "_save(silent=True)", "Supprimer une analyse", "disable_default_buttons"):
        assert token in src_w, f"fenêtre refs : {token} absent"
    # ANTI-CRASH chat : worker fini PARQUE via abandon_thread (jamais déréférencé à chaud)
    assert src_w.count("abandon_thread(_chat_worker[0])") >= 2, "chat : worker non parqué"
    # 3b. Bouton « Charger une analyse » dans la section (accessible sans images)
    src_load = inspect.getsource(PageScenario._on_load_saved_analysis)
    assert "ref_library" in src_load and "_apply_saved_analysis" in src_load
    src_apply = inspect.getsource(PageScenario._apply_saved_analysis)
    assert "_open_refs_window" in src_apply and "_save(silent=True)" in src_apply, \
        "chargement → persistance projet + fenêtre (chat inclus)"
    # 4. Chat DA Cinéma : worker streaming dédié (calibré film, anti-troncature)
    from api.screenplay import RefsChatWorker, _REFS_CHAT_SYSTEM
    w = RefsChatWorker([{"role": "user", "content": "?"}], "analyse", "scénario")
    assert hasattr(w, "chunk") and hasattr(w, "done") and hasattr(w, "failed")
    _run = inspect.getsource(RefsChatWorker.run)
    assert "chat_stream" in _run and "max_tokens=8192" in _run, "chat : streaming + 8192 tokens"
    assert "jamais à copier" in _REFS_CHAT_SYSTEM and "FILM" in _REFS_CHAT_SYSTEM
    # 5. DA injectée : application des suggestions + session de co-écriture (l'arrangement
    # l'avait déjà via ref_analysis=). Le dialog la passe à chaque tour de chat.
    from api.screenplay import ApplyArrangeWorker, ArrangeChatWorker
    assert "refs_analysis" in inspect.signature(ApplyArrangeWorker.__init__).parameters, \
        "ApplyArrangeWorker : DA injectable"
    assert "refs_analysis" in inspect.signature(ArrangeChatWorker.__init__).parameters, \
        "ArrangeChatWorker : DA injectable"
    from ui.dialog_arrange_session import ArrangeSessionDialog
    assert "refs_analysis" in inspect.signature(ArrangeSessionDialog.__init__).parameters, \
        "session de co-écriture : DA injectable"
    src_page = inspect.getsource(__import__("ui.page_scenario", fromlist=["_"]))
    assert src_page.count("refs_analysis=self._last_ref_analysis") >= 2, \
        "page : DA passée à l'application ET à la session de co-écriture"
    src_dlg = inspect.getsource(__import__("ui.dialog_arrange_session", fromlist=["_"]))
    assert "refs_analysis=self._refs_analysis" in src_dlg, \
        "dialog : DA passée au worker de chat"


@test
def decoupage_cinema_deterministe_depuis_mise_en_page():
    """Règle portée du Live (2026-07-13) : une Mise en page PANDORA structurée
    (« PLAN n — … ») se convertit en plans storyboard SANS appel IA — prompts
    co-écrits repris TELS QUELS, zéro perte, zéro reformulation. L'avertissement de
    réécriture n'apparaît QUE si le chemin repasse réellement par l'IA."""
    import core.decoupage_layout as dl
    from api.screenplay import GenerateStoryboardWorker
    layout = "\n".join(
        ["=== ACTE 1 — Ouverture ==="] +
        sum(([f"PLAN {n} — Titre {n}",
              f"Durée : {4 + n % 9}s · Valeur de plan : Plan moyen · Mouvement : Panoramique",
              f'PROMPT VIDÉO (français) : "vidéo {n} co-écrite"',
              f'PROMPT SON (sound design / SFX, français) : "son {n}"']
             for n in range(1, 24)), []))
    shots = dl.layout_segments_to_cinema_shots(layout)
    assert len(shots) == 23, f"convertisseur : {len(shots)}/23 (perte)"
    s0 = shots[0]
    assert s0["scene_title"] == "Titre 1" and s0["seedance_prompt"] == "vidéo 1 co-écrite" \
        and s0["sound_prompt"] == "son 1" and s0["shot_size"] == "Plan moyen" \
        and s0["camera_movement"] == "Panoramique" and s0["seq_num"] == 1, \
        "champs du plan non repris de la mise en page"
    assert s0["character_ids"] == [] and s0["decor_id"] == "" and s0["merged"] is False, \
        "défauts sûrs attendus pour les champs non couverts"
    # Worker : source structurée → plans SANS appel IA (aucune clé requise, branche
    # AVANT key_error — c'est ce qui prouve le zéro-coût).
    w = GenerateStoryboardWorker(layout); cap = {}
    w.finished.connect(lambda s: cap.__setitem__("s", s))
    w.failed.connect(lambda e: cap.__setitem__("f", e))
    w.run()
    assert "f" not in cap and len(cap.get("s", [])) == 23, \
        f"worker : mise en page 23 plans → 23 plans sans IA (obtenu {len(cap.get('s', []))})"
    assert cap["s"][4]["seedance_prompt"] == "vidéo 5 co-écrite", "prompt co-écrit reformulé !"
    # Durée : plafond Seedance 15 s conservé même sur une mise en page trop longue.
    _long = dl.layout_segments_to_cinema_shots(
        'PLAN 1 — X\nDurée : 40s · Valeur de plan : Large\nPROMPT VIDÉO (français) : "v"')
    assert _long and _long[0]["duration"] == 15.0, "durée non plafonnée à 15 s"
    # Les 2 pages n'avertissent QUE si la mise en page n'est PAS parsable (chemin IA).
    from ui.page_scenario import PageScenario as _PS
    _src = inspect.getsource(_PS._on_storyboard)
    assert "is_structured_layout" in _src and "confirm_prompt_rewrite" in _src, \
        "page Scénario : avertissement non conditionné au chemin IA"
    from ui.page_storyboard import PageStoryboard as _PSB
    _oa = inspect.getsource(_PSB._on_analyze)
    assert "is_structured_layout" in _oa and "confirm_prompt_rewrite" in _oa, \
        "page Storyboard : avertissement non conditionné au chemin IA"


@test
def colonne_langues_dialogues():
    """Colonne « Langues » (storyboard Cinéma) : choix par plan, défaut anglais ;
    dialogues traduits À L'ENVOI uniquement (pas dans le prompt affiché)."""
    import ui.page_storyboard as M
    assert len(M._COLS) == 21, \
        "Langues (16) · Nom du plan (17) · boutons (18) · Hauteur (19) · Référence (20) = 21 colonnes"
    assert M._COLS[20][0] == "Référence", "colonne Référence (inspiration) en logique 20"
    assert M._DEFAULT_COL_ORDER.index(20) == M._DEFAULT_COL_ORDER.index(1) + 1, \
        "Référence affichée juste après Mood"
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
    # Audit prompts 2026-07-02 : plus de mots qualité génériques interdits
    # (« 4K/film grain/high quality » poussaient un rendu contradictoire).
    assert "cinematic still frame" in p and "4K" not in p, "suffixe mood assaini"
    assert "Marche en forêt" in p, "description d'action présente"
    assert "OPENING state" not in p, "pas de consigne keyframe Live côté Cinéma"


@test
def moteurs_storyboard_filtres():
    """Générer depuis Storyboard : combo ouvert aux moteurs compatibles, t2v purs
    écartés ; libellés du combo SANS « keyframes » par défaut, Seedance 2.0
    « recommandé ». Depuis 2026-06-25, l'enchaînement des moods (mood i en début →
    mood i+1 en fin) est POSSIBLE en Cinéma via le toggle RENDU & AUDIO
    « Enchaîner les moods » — mais SANS reprendre le mécanisme Live
    `_get_mapping_keyframes`."""
    import ui.tab_t2v as t2v
    src = inspect.getsource(t2v)
    assert "use_keyframes=False" in src, "libellés du combo sans keyframes par défaut"
    assert 'recommended=("seedance-2.0",)' in src, "Seedance 2.0 recommandé"
    assert "_get_mapping_keyframes" not in src, "pas le mécanisme keyframes Live"
    assert "_mood_chain_cb" in src and "end_image_path" in src, \
        "enchaînement des moods (début/fin) disponible via RENDU & AUDIO"
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
def drone_fpv_et_moods_keyframes():
    """Drone FPV (mouvement storyboard + prompt typé distinct) + Seedance 1.5 / LTX-2
    ouverts à « Générer depuis le storyboard » + enchaînement des moods (mood i en
    début → mood i+1 en fin) réservé aux moteurs « image de fin » (2026-06-25)."""
    from core.storyboard import CAMERA_MOVEMENTS
    from core.camera_data import shot_movement_to_prompt
    assert "Drone FPV" in CAMERA_MOVEMENTS, "mouvement Drone FPV présent au storyboard"
    fpv = shot_movement_to_prompt("Drone FPV")
    assert "FPV" in fpv and fpv != shot_movement_to_prompt("Grue / Drone"), \
        "prompt Drone FPV typé et distinct du drone classique"
    from core.engine_caps import ENGINE_CAPS, workflow_compatible
    assert ENGINE_CAPS["seedance-1.5-pro"]["end_frame"], "Seedance 1.5 = image de fin"
    assert not ENGINE_CAPS["ltx-2"]["end_frame"], "LTX-2 = i2v sans image de fin"
    assert workflow_compatible("seedance-1.5-pro") and workflow_compatible("ltx-2")
    import ui.tab_t2v as t2v
    keys = [k for _, k in t2v._ENGINES]
    assert "seedance-1.5-pro" in keys and "ltx-2" in keys, "moteurs ajoutés au menu"


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
                         "sync_staging", "sync_lighting",
                         "sync_casting", "sync_accessories", "sync_vehicles"}, \
        "options de synchronisation (dont casting / accessoires / véhicules)"
    assert not opts["sync_casting"] and not opts["sync_accessories"] \
        and not opts["sync_vehicles"], "casting / accessoires / véhicules décochés par défaut"
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
    assert set(ap.ENGINES) == {"claude", "opus", "haiku", "fable5", "gpt",
                               "mistral", "kimi", "glm", "ollama"}
    assert ap.ENGINES["glm"]["provider"] == "glm", "GLM (Zhipu) — API ou local"
    assert ap.ENGINES["gpt"]["provider"] == "openai"
    assert ap.ENGINES["opus"]["creative_model"] == "claude-opus-4-8"
    # Profil PANDORA optimisé (défaut) : moteur IDÉAL par tâche — Opus UNIQUEMENT
    # pour le storyboard, Sonnet pour scénario/sync, Haiku pour le reste (économe).
    assert ap.PANDORA_OPTIMIZED["storyboard_gen"] == "opus", "storyboard = Opus"
    assert ap.PANDORA_OPTIMIZED["extraction"] == "claude", "extraction = Sonnet 5 (pas Opus)"
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
    ap._cfg = lambda: {"ai_provider": "anthropic", "ai_model_creative": "claude-sonnet-5",
                       "ai_task_engines": {"enhance": "gpt", "storyboard_chat": "fable5"}}
    try:
        assert ap._resolve_engine("enhance") == ("openai", "")
        assert ap._resolve_engine("storyboard_chat") == ("anthropic", "claude-fable-5")
        assert ap._resolve_engine("assistant") == ("anthropic", "claude-sonnet-5")
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
def moteur_kimi_api_ou_local():
    """Kimi K2.7 (Moonshot) : moteur compatible OpenAI, URL de base éditable qui sert
    d'aiguillage API cloud ↔ serveur local ; clé exigée seulement en cloud ; modèle
    défaut kimi-k2.7-code ; câblé dans Paramètres Cinéma (sélecteur + clé + testeur)."""
    import core.ai_provider as ap
    assert "kimi" in ap._PROVIDERS
    assert ap.ENGINES["kimi"]["provider"] == "kimi"
    assert ap.ENGINES["kimi"]["name"] == "Kimi K2.7"
    assert "kimi" in ap.ENGINE_ORDER
    assert ap._KIMI_DEFAULT_MODEL == "kimi-k2.7-code"
    assert ap._KIMI_DEFAULT_URL == "https://api.moonshot.ai/v1"
    orig = ap._cfg
    try:
        # Routage par tâche → provider kimi
        ap._cfg = lambda: {"ai_task_engines": {"screenplay": "kimi"}}
        assert ap._resolve_engine("screenplay")[0] == "kimi"
        # Modèle : défaut + override
        ap._cfg = lambda: {}
        assert ap._model("creative", "kimi", "") == "kimi-k2.7-code"
        ap._cfg = lambda: {"kimi_model": "kimi-k2.6"}
        assert ap._model("utility", "kimi", "") == "kimi-k2.6"
        # key_error : cloud SANS clé → erreur ; AVEC clé → None ; local → None
        ap._cfg = lambda: {"ai_task_engines": {"sync": "kimi"}}
        assert ap.key_error("sync") and "Kimi" in ap.key_error("sync")
        ap._cfg = lambda: {"ai_task_engines": {"sync": "kimi"}, "kimi_key": "sk-x"}
        assert ap.key_error("sync") is None
        ap._cfg = lambda: {"ai_task_engines": {"sync": "kimi"},
                           "kimi_url": "http://localhost:11434/v1"}
        assert ap.key_error("sync") is None, "local ne doit pas exiger de clé"
        # Payload OpenAI-compatible : URL /chat/completions, modèle, Bearer
        ap._cfg = lambda: {"kimi_key": "sk-xyz"}
        url, payload, headers = ap._kimi_payload("S", [{"role": "user", "content": "h"}],
                                                 "kimi-k2.7-code", 99, False)
        assert url == "https://api.moonshot.ai/v1/chat/completions"
        assert payload["model"] == "kimi-k2.7-code" and payload["max_tokens"] == 99
        assert headers["Authorization"] == "Bearer sk-xyz"
        # Local sans clé → Bearer factice 'local' + URL repointée
        ap._cfg = lambda: {"kimi_url": "http://localhost:11434/v1"}
        url2, _, h2 = ap._kimi_payload("", [{"role": "user", "content": "x"}], "m", 1, True)
        assert url2 == "http://localhost:11434/v1/chat/completions"
        assert h2["Authorization"] == "Bearer local"
        # Dispatch : provider kimi routé vers les adaptateurs Kimi
        ds = inspect.getsource(ap._dispatch_complete) + inspect.getsource(ap._dispatch_stream)
        assert ds.count('provider == "kimi"') == 2
        # Nom d'affichage
        assert ap._engine_display_name("kimi", "") == "Kimi K2.7"
    finally:
        ap._cfg = orig
    # Paramètres Cinéma : sélecteur Kimi + champs URL/modèle + clé + testeur
    src_pg = inspect.getsource(__import__("ui.page_settings", fromlist=["_"]))
    assert '"kimi"' in src_pg and "kimi_url_input" in src_pg and "kimi_model_input" in src_pg
    assert "self.kimi_input" in src_pg and "test_kimi_connection" in src_pg
    assert '"kimi_key"' in src_pg and '"kimi_url"' in src_pg and '"kimi_model"' in src_pg
    # i18n : libellés Kimi traduits FR→EN
    import core.i18n as i18n
    assert "✓  Tester API Kimi" in i18n._FR_TO_EN
    assert "Modèle Kimi (défaut : kimi-k2.7-code)" in i18n._FR_TO_EN


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
    # Mise en forme façon Word (2026-07-07) : texte CENTRÉ dans la colonne de lecture
    # bornée (lisible car largeur limitée — PAS le centrage pleine largeur illisible).
    from PyQt6.QtCore import Qt as _Qt
    _ed_align = p._editor_text.document().defaultTextOption().alignment()
    _lv_align = p._layout_view.document().defaultTextOption().alignment()
    assert _ed_align & _Qt.AlignmentFlag.AlignHCenter, "Scénario centré dans la colonne (façon Word)"
    assert _lv_align & _Qt.AlignmentFlag.AlignHCenter, "Mise en page centrée dans la colonne"
    assert hasattr(p._editor_text, "_reading_column_filter") \
        and hasattr(p._layout_view, "_reading_column_filter"), \
        "colonne de lecture centrée installée sur les 2 onglets"
    assert p._editor_tabs.isTabEnabled(1) and p._editor_tabs.currentIndex() == 1
    assert p._current.get("layout_content"), "mise en page persistée séparément"
    # ── Source du découpage AUTOMATIQUE (règle 2026-07-09, aucun choix manuel) ──
    # Mise en page PANDORA si présente…
    assert p._decoupage_base() == "MISE EN PAGE PANDORA", \
        "le découpage part de la Mise en page PANDORA quand elle existe"
    assert "MISE EN PAGE PANDORA" in p._text_with_music() \
        and "SCENARIO ORIGINAL" not in p._text_with_music(), \
        "_text_with_music doit injecter la mise en page, pas le scénario brut"
    # …sinon le scénario.
    p._layout_view.setPlainText("")
    assert p._decoupage_base() == "SCENARIO ORIGINAL", "sans mise en page → scénario"
    p._layout_view.setPlainText("MISE EN PAGE PANDORA")
    # En Cinéma la génération passe par l'IA (qui REFORMULE) → si une mise en page
    # existe, _on_storyboard AVERTIT (confirm_prompt_rewrite) ; plus AUCUN choix manuel.
    _obs = inspect.getsource(PageScenario._on_storyboard)
    assert "confirm_prompt_rewrite" in _obs, \
        "_on_storyboard Cinéma : avertissement de réécriture absent"
    assert "choose_decoupage_source" not in _obs, \
        "_on_storyboard Cinéma : l'ancienne fenêtre de choix doit avoir disparu"
    # La fenêtre de mise en page applique vers l'onglet (pas _set_editor_text)
    fw = inspect.getsource(PageScenario._open_format_window)
    assert "_apply_layout" in fw and "_set_editor_text" not in fw, \
        "la fenêtre Mise en page écrit dans l'onglet dédié"
    # Plus de colonne fixe 900 px collée à gauche : colonne de lecture centrée
    be = inspect.getsource(PageScenario._build_editor)
    assert "setFixedWidth(900)" not in be, "plus de colonne 900 px collée à gauche"
    assert "install_reading_column" in be, "colonne de lecture centrée (lignes lisibles)"


@test
def avertissement_reecriture_dialog():
    """Dialogue d'avertissement de réécriture (ui/decoupage_dialogs, partagé Cin/Live,
    2026-07-09) : défaut = NE PAS continuer ; « Continuer » → ok=True ; l'ancienne
    fenêtre de CHOIX de source a disparu (source AUTOMATIQUE : mise en page sinon brut)."""
    from ui.decoupage_dialogs import _RewriteWarningDialog, confirm_prompt_rewrite
    d = _RewriteWarningDialog(None)
    assert d.ok is False, "défaut : ne pas continuer"
    d._btn_cont.click()
    assert d.ok is True, "« Continuer » doit valider"
    assert callable(confirm_prompt_rewrite)
    import ui.decoupage_dialogs as _dd
    assert not hasattr(_dd, "choose_decoupage_source"), \
        "l'ancienne fenêtre de choix de source doit avoir disparu (source automatique)"


@test
def placeholder_decoupage_source_cinema():
    """Placeholder « ⊕ Générer depuis le scénario » (Storyboard Cinéma, découpage vide) :
    source AUTOMATIQUE (Mise en page PANDORA sinon scénario) + AVERTISSEMENT de
    réécriture si une mise en page existe (l'IA reformule) — règle 2026-07-09."""
    import inspect
    from ui.page_storyboard import PageStoryboard
    _oa = inspect.getsource(PageStoryboard._on_analyze)
    assert 'sc.get("layout_content"' in _oa and "_layout or _source" in _oa, \
        "placeholder Cinéma : source automatique (layout sinon scénario) non branchée"
    assert "confirm_prompt_rewrite" in _oa, \
        "placeholder Cinéma : avertissement de réécriture absent"
    assert "choose_decoupage_source" not in _oa, \
        "placeholder Cinéma : l'ancienne fenêtre de choix doit avoir disparu"
    # Le bouton placeholder « ⊕ Générer depuis le scénario » est bien relié à _on_analyze.
    _mod = inspect.getsource(__import__("ui.page_storyboard", fromlist=["_"]))
    assert "Générer depuis le scénario" in _mod and "self._on_analyze" in _mod, \
        "bouton placeholder Cinéma non relié à _on_analyze"


@test
def colonne_lecture_largeur_limitee():
    """Colonne de lecture (2026-07-06) : sur un large éditeur, largeur LIMITÉE (~820 px)
    et CENTRÉE via les marges LATÉRALES du frame (pas verticales → le texte reste en
    haut) ; petite respiration entre paragraphes (marge basse de bloc)."""
    from PyQt6.QtWidgets import QMainWindow, QTextEdit, QApplication
    from ui.widgets import install_reading_column, apply_paragraph_spacing
    win = QMainWindow(); te = QTextEdit()
    install_reading_column(te, max_width=820)
    te.setPlainText("Bloc A.\nBloc B un peu plus long pour la démonstration de la colonne.")
    apply_paragraph_spacing(te, 10)
    win.setCentralWidget(te); win.resize(1600, 600); win.show()
    for _ in range(6):
        QApplication.processEvents()
    doc = te.document()
    vw = te.viewport().width()
    if vw > 1200:   # si le WM headless donne bien une large fenêtre
        side = int(doc.rootFrame().frameFormat().leftMargin())
        col = vw - 2 * side - 2 * int(doc.documentMargin())
        assert side > 150, f"colonne pas centrée (marge latérale {side})"
        assert 760 <= col <= 880, f"colonne pas ~820 px (={col})"
    # center=True → texte centré dans la colonne (façon Word, 2026-07-07).
    from PyQt6.QtCore import Qt as _QtC
    te2 = QTextEdit()
    install_reading_column(te2, max_width=820, center=True)
    te2.setPlainText("Centré A.\nCentré B.")
    apply_paragraph_spacing(te2)   # center déduit du marqueur _reading_center
    assert te2.document().defaultTextOption().alignment() & _QtC.AlignmentFlag.AlignHCenter, \
        "install_reading_column(center=True) → texte centré"
    # Marge verticale PETITE (le texte ne descend pas de 387 px sous le titre).
    assert int(doc.documentMargin()) <= 40, "marge verticale trop grande (setDocumentMargin ?)"
    # Respiration entre paragraphes appliquée.
    assert doc.firstBlock().blockFormat().bottomMargin() >= 8, "pas de respiration entre paragraphes"
    win.close()


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
    # Anti-trames v2 : yadif SEULEMENT si la vidéo est RÉELLEMENT entrelacée
    # (field_order + confirmation idet) — jamais sur du progressif mal flagué.
    assert "video_is_interlaced" in vsrc, "désentrelacement conditionnel (détection réelle)"
    assert "min(1080,ih)" in vsrc, "plafond 1080p (tous moteurs)"
    assert callable(getattr(vu, "video_is_interlaced", None)), "détection d'entrelacement exposée"
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
    for k in ("seedream5", "seedream45", "zimage", "qwen_image", "nb2_lite", "ideogram4"):
        assert k in eng.ENGINES, f"moteur image {k} manquant"
    ep, _a, _ = eng.build_request("seedream5", "x", (1024, 768), "1K", [])
    assert ep == "fal-ai/bytedance/seedream/v5/lite/text-to-image"
    ep2, a2, _ = eng.build_request("seedream5", "x", (1024, 768), "1K", ["data:img"])
    assert ep2.endswith("/edit") and "image_urls" in a2, "Seedream 5 édition (refs)"
    # Nano Banana 2 Lite : endpoint owner-préfixé + 1024² fixe (pas de 'resolution')
    epl, al, _ = eng.build_request("nb2_lite", "x", (1024, 1024), "1K", [])
    assert epl == "google/nano-banana-2-lite" and "resolution" not in al
    epl2, al2, _ = eng.build_request("nb2_lite", "x", (1024, 1024), "1K", ["data:img"])
    assert epl2 == "google/nano-banana-lite/edit" and "image_urls" in al2
    # Ideogram v4 : slug owner-préfixé + schéma ideogram (rendering_speed)
    epi, ai, _ = eng.build_request("ideogram4", "x", (1024, 768), "1K", [])
    assert epi == "ideogram/v4" and ai.get("rendering_speed") == "QUALITY"

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
        for w in ("Seedance15Worker", "LTX2Worker", "Wan27Worker", "Hailuo23Worker",
                  "Seedance20MiniWorker", "GeminiOmniFlashWorker", "GrokVideoWorker"):
            assert w in dsrc, f"{mod}: dispatch {w} manquant"

    # — TTS : registre + workers + page Doublage (3e mode + moteur de clonage) —
    import api.tts as tts
    assert len(tts.SPEECH_ENGINES) == 7 and "minimax-2.8-hd" in tts.SPEECH_ENGINES
    # ElevenLabs Eleven v3 (FR natif) + language_code='fr' forcé via 'extra'
    assert "elevenlabs-v3" in tts.SPEECH_ENGINES
    assert tts.SPEECH_ENGINES["elevenlabs-v3"].get("extra", {}).get("language_code") == "fr"
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
        assert _mf("extraction", "creative", d) == "claude-sonnet-5", "extraction = Sonnet 5"
        assert _mf("screenplay", "creative", d) == "claude-sonnet-5", "scénario = Sonnet"
        assert _mf("sync", "creative", d) == "claude-sonnet-5", "sync = Sonnet"
        assert _mf("translate", "utility", d) == "claude-haiku-4-5", "traduction = Haiku"
        # Config vide → même routage intelligent.
        assert _mf("storyboard_gen", "creative", {}) == "claude-opus-4-8"
        assert _mf("extraction", "creative", {}) == "claude-sonnet-5"
        # Global explicite → s'applique partout (Sonnet pour TOUTES les tâches).
        g = {"ai_provider": "anthropic", "ai_model_creative": "claude-sonnet-5"}
        assert _mf("storyboard_gen", "creative", g) == "claude-sonnet-5"
        assert _mf("extraction", "creative", g) == "claude-sonnet-5"
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
    # Audit prompts 2026-07-02 : noms d'éléments entre « » (robuste traduction).
    assert "à gauche de « la table »" in st._actor_placement_phrase(rec, rec["actors"][0])
    rec["actors"][0]["x"] = 0.70
    assert "à droite de « la table »" in st._actor_placement_phrase(rec, rec["actors"][0])
    rec["actors"][0].update(x=0.50, y=0.50)
    assert st._actor_placement_phrase(rec, rec["actors"][0]).startswith(
        "tout contre « la table »")
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
    # (2b) Axe caméra déduit de la POSITION : déplacer la caméra change l'axe du plan.
    assert st.axis_from_placement({"camera": {"x": .5, "y": .9}, "actors": [{"x": .5, "y": .5}]}) == "Face"
    assert st.axis_from_placement({"camera": {"x": .5, "y": .1}, "actors": [{"x": .5, "y": .5}]}) == "Dos"
    assert st.axis_from_placement({"camera": {"x": .9, "y": .5}, "actors": [{"x": .5, "y": .5}]}) == "Latéral 90°"
    assert "axis_from_placement" in pst, "l'axe du storyboard suit la position caméra"
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
    # HABILLAGE comme Conducteur/Scénario (retour Matthieu 2026-07-05) : fond du
    # Studio IA = NOIR (bg0), le panneau IA (chat) reste BLEU MARINE (bg1, via
    # objectName iaChatPanel), poignée COLLÉE au bord droit (marge droite = 0).
    with open(os.path.join(root, "studio_images", "styles.py"), encoding="utf-8") as f:
        ss = f.read()
    assert "background-color: {CP['bg0']}" in ss, "fond Studio Images = bg0 (noir), comme Conducteur/Scénario"
    assert "iaChatPanel" in src, "panneau IA doit rester bleu marine (bg1, objectName iaChatPanel)"
    assert "root.setContentsMargins(14, 12, 0, 12)" in src, "poignée non collée au bord (marge droite ≠ 0)"
    # Panneau chat ENTIÈREMENT marine — viewport du scroll peint aussi (sinon bande
    # noire en haut) ; poignée « IA » collée au bord (spacer masqué sur la page
    # « seedance »). Retour Matthieu 2026-07-05.
    assert "viewport().setStyleSheet" in src, "viewport du chat non peint → bande noire résiduelle"
    with open(os.path.join(root, "ui", "pandora_window.py"), encoding="utf-8") as f:
        assert 'key != "seedance"' in f.read(), "spacer non masqué sur Studio IA → poignée IA décalée"


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


@test
def plans_recurrents_libelles():
    """Storyboard : libellé couleur manuel (clic droit) + détection des plans
    RÉCURRENTS par séquence (cœur déterministe + worker IA Haiku, repli déterministe),
    une couleur distincte par groupe, sélectionnable d'un bloc (Rendu/Audio)."""
    import inspect
    import core.storyboard as sb
    import core.recurrence as rec
    # Cœur déterministe : champ/contrechamp dans UNE séquence → 2 groupes ; plan
    # unique ignoré ; autre séquence non mélangée.
    shots = [
        {"id": "a", "seq_num": 1, "decor_id": "d", "camera_axis": "Face",  "character_ids": ["j"]},
        {"id": "b", "seq_num": 1, "decor_id": "d", "camera_axis": "Dos",   "character_ids": ["m"]},
        {"id": "c", "seq_num": 1, "decor_id": "d", "camera_axis": "Face",  "character_ids": ["j"]},
        {"id": "d", "seq_num": 1, "decor_id": "d", "camera_axis": "Dos",   "character_ids": ["m"]},
        {"id": "e", "seq_num": 1, "decor_id": "d", "camera_axis": "Large", "character_ids": []},
        {"id": "f", "seq_num": 2, "decor_id": "d", "camera_axis": "Face",  "character_ids": ["j"]},
    ]
    assert rec.group_recurrent(shots) == [["a", "c"], ["b", "d"]]
    assert sb.recurrent_color(0) != sb.recurrent_color(1), "couleurs distinctes par groupe"
    assert len(sb.LABEL_COLORS) >= 4 and hasattr(sb, "set_label") and hasattr(sb, "set_recurrent")
    csb = inspect.getsource(sb)
    assert 'setdefault("label_color"' in csb and 'setdefault("recurrent_color"' in csb, \
        "champs séparés : libellé esthétique vs flag récurrent"
    # Le flag récurrent (set_recurrent) est distinct du libellé esthétique (set_label).
    assert "set_recurrent" in inspect.getsource(rec), "détection pose le FLAG récurrent"
    # Worker IA : signal « done » (PAS « finished ») + repli déterministe.
    scr = inspect.getsource(__import__("api.screenplay", fromlist=["_"]))
    assert ("class AnalyzeRecurrentShotsWorker" in scr and "done   = pyqtSignal" in scr
            and "group_recurrent" in scr), "worker IA récurrents + repli déterministe"
    # UI Storyboard : 2 repères distincts (libellé esthétique + flag récurrent de coin).
    ps = inspect.getsource(__import__("ui.page_storyboard", fromlist=["_"]))
    assert ("Libellé couleur" in ps and "Plan récurrent" in ps and "_set_label" in ps
            and "_set_recurrent" in ps and "recurrent_color" in ps
            and "_on_detect_recurrent" in ps), "libellé esthétique + flag récurrent + bouton"
    # Sélecteur Rendu/Audio : sélection par GROUPE récurrent (flag).
    t2 = inspect.getsource(__import__("ui.tab_t2v", fromlist=["_"]))
    assert ("_select_color_group" in t2 and "_rebuild_group_chips" in t2
            and "recurrent_color" in t2), "sélection par groupe récurrent"
    # Auto à la génération (baseline déterministe).
    pg = inspect.getsource(__import__("ui.page_scenario", fromlist=["_"]))
    assert "detect_and_apply" in pg, "coloration auto à la génération"


@test
def moods_nano_banana_cinema():
    """Moods : CINÉMA → Nano Banana 2 (réfs portraits persos + image décor) ;
    LIVE → Flux (inchangé). Distinction par le namespace storyboard, sans sélecteur."""
    import inspect
    import core.storyboard as sb
    import api.apercu as ap
    ns0 = sb.get_namespace()
    try:
        sb.set_namespace("storyboard")
        assert ap._is_cinema_mood() is True, "Cinéma → NB2"
        sb.set_namespace("live_seq_live")
        assert ap._is_cinema_mood() is False, "Live → Flux"
        # Routage run_mood (sans réseau) : capture le backend appelé.
        calls = {}
        _nb2, _flux = ap.run_generation_nb2, ap.run_generation
        ap.run_generation_nb2 = lambda *a, **k: calls.setdefault("nb2", True) or ""
        ap.run_generation     = lambda *a, **k: calls.setdefault("flux", True) or ""
        try:
            sb.set_namespace("storyboard")
            ap.run_mood({}, "p", ".", "k", lambda *_: None)
            assert calls == {"nb2": True}, calls
            calls.clear()
            sb.set_namespace("live_seq_live")
            ap.run_mood({}, "p", ".", "k", lambda *_: None, building_ref="b")
            assert calls == {"flux": True}, calls
        finally:
            ap.run_generation_nb2, ap.run_generation = _nb2, _flux
        # NB2 = édition avec réfs persos + décor.
        src = inspect.getsource(ap)
        assert ("nano-banana-2/edit" in src and "_shot_ref_images" in src
                and "image_urls" in src), "NB2 envoie les réfs persos + décor"
    finally:
        sb.set_namespace(ns0)


@test
def raccord_pas_injecte_dans_prompt():
    """Cinéma : l'encart « Raccord automatique » n'injecte PLUS le raccord dans le
    prompt du storyboard (il dégradait le découpage). Le raccord reste cochable dans
    RENDU & AUDIO (_raccord_auto_cb → I2V dernière frame du plan précédent)."""
    import inspect
    from ui.tab_t2v import _ContinuityBar
    bar = _ContinuityBar()
    bar._prev_shot = {"decor_name": "X", "scene_title": "Y"}
    try:
        bar._cb.setChecked(True)
    except Exception:
        pass
    assert bar.build_continuity_prefix() == "", "raccord ne s'injecte plus dans le prompt"
    src = inspect.getsource(__import__("ui.tab_t2v", fromlist=["_"]))
    assert "_ez_lay.addWidget(self._continuity_bar)" not in src, "encart retiré de l'UI"
    assert "_raccord_auto_cb" in src, "raccord toujours cochable dans RENDU & AUDIO"


@test
def enhance_ameliorer_retire_partout():
    """« Améliorer le prompt » (☁ / case auto) RETIRÉ partout : composant partagé
    prompt_block (bouton + auto cachés) + dialogs casting/décor/HMC/accessoire/
    véhicule/plan + onglets vidéo + pop-up prompt (param `enhance` ignoré)."""
    import os as _os
    from ui.widgets import prompt_block
    _f, _ta, cloud, auto = prompt_block(placeholder="x")
    assert cloud.isHidden() and not auto.isChecked(), "bouton Améliorer caché + auto désactivé"
    root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    for rel in ("ui/dialog_character.py", "ui/dialog_decor.py", "ui/dialog_hmc.py",
                "ui/dialog_accessory.py", "ui/dialog_vehicle.py", "ui/dialog_shot.py",
                "ui/tab_video_engines.py", "ui/tab_davinci_edit.py", "ui/tab_reference.py"):
        with open(_os.path.join(root, rel), encoding="utf-8") as f:
            src = f.read()
        assert 'QLabel("Améliorer le prompt")' not in src, f"libellé Améliorer encore actif : {rel}"
    # Pop-up prompt : bloc « ✦ Améliorer » neutralisé.
    with open(_os.path.join(root, "ui", "page_storyboard.py"), encoding="utf-8") as f:
        assert "param `enhance` ignoré" in f.read(), "bouton Améliorer du pop-up prompt retiré"


@test
def variations_decor_par_groupe():
    """« Créer des variations » sur une PIÈCE : depuis la page Décors, le bandeau de
    pièce ouvre une fenêtre (prompt éditable) qui régénère TOUTES ses vues (groupe
    entier) via le moteur 7 vues ; l'ancienne image de chaque vue est gardée en
    variante."""
    import inspect
    from ui.dialog_room_variations import RoomVariationsDialog, _CODE_TO_RV
    decors = [
        {"id": "o", "room_group": "SAM", "room_view": "Ensemble", "prompt": "base"},
        {"id": "a", "room_group": "SAM", "room_view": "Avant", "prompt": "x"},
    ]
    dlg = RoomVariationsDialog(None, "SAM", decors)
    # Garde-fou anti-crash : le signal NE doit PAS s'appeler « done » (masquerait
    # QDialog.done() → « native Qt signal is not callable » à la fermeture).
    assert callable(dlg.done), "QDialog.done() doit rester callable (signal mal nommé)"
    assert hasattr(dlg, "created"), "signal renommé en « created »"
    dlg.reject()  # le geste qui plantait — ne doit pas lever
    assert dlg._prompt.toPlainText() == "base", "prompt pré-rempli depuis la vue d'ensemble"
    assert _CODE_TO_RV["ensemble"] == "Ensemble" and _CODE_TO_RV["sol"] == "Sol"
    assert hasattr(dlg, "_btn_gen")
    pd = inspect.getsource(__import__("ui.page_decors", fromlist=["_"]))
    assert ("_on_room_variations" in pd and "RoomVariationsDialog" in pd
            and "Variations" in pd), "bouton Variations sur le bandeau de pièce"
    src = inspect.getsource(__import__("ui.dialog_room_variations", fromlist=["_"]))
    assert ("GenerateRoomViewsWorker" in src and "generated_images" in src), \
        "régénère via le moteur 7 vues + garde l'ancienne image en variante"


@test
def sauver_ouvrir_elements():
    """Castings/Décors/Accessoires/HMC/Véhicules : deux boutons « Sauvegarder » /
    « Ouvrir » à côté de la barre de recherche (même principe que le storyboard).
    core.element_io fait l'aller-retour JSON ; l'ouverture REMPLACE les éléments
    du projet courant (delete_fn ne touche que l'index, pas les images)."""
    import inspect, os as _o, tempfile as _tf
    import core.element_io as eio

    # 1) Logique pure (fonctions en mémoire — aucun disque/config réel touché).
    store = [{"id": "a", "name": "A", "project_id": "P"},
             {"id": "b", "name": "B", "project_id": "P"}]

    def _list(): return [dict(x) for x in store]

    def _save(d):
        d = dict(d)
        if not d.get("id"):
            d["id"] = "n%d" % (len(store) + 1)
        store.append(d)
        return d

    def _del(iid): store[:] = [x for x in store if x.get("id") != iid]

    path = _o.path.join(_tf.gettempdir(), "pandora_test_eio.json")
    eio.export_items(path, "casting", _list())
    store[:] = [{"id": "z", "name": "Z", "project_id": "P"}]   # remplace
    n = eio.import_items(path, "casting", _list, _save, _del)
    assert n == 2 and sorted(x["name"] for x in store) == ["A", "B"], (n, store)
    # Garde-fou : un fichier « casting » refusé dans une page « decors ».
    try:
        eio.read_items(path, "decors")
        assert False, "type incompatible non détecté"
    except ValueError:
        pass
    assert eio.file_suffix("vehicles") == "vehicules"
    # Dossier de sauvegarde DÉDIÉ par type (pas la racine du projet).
    for _k, _folder in (("casting", "Casting"), ("decors", "Décors"),
                        ("accessories", "Accessoires"), ("hmc", "HMC"),
                        ("vehicles", "Véhicules")):
        d = eio.saves_dir(_k)
        assert d.rstrip("/\\").endswith(_folder) and _o.path.isdir(d), \
            f"dossier dédié « {_folder} » absent"

    # 2) Helper UI commun + branchement des 5 pages (inspection source : robuste).
    from ui.element_io_buttons import make_save_open_buttons  # noqa: F401
    expect = {
        "ui.page_castings":    "casting",
        "ui.page_decors":      "decors",
        "ui.page_accessories": "accessories",
        "ui.page_hmc":         "hmc",
        "ui.page_vehicles":    "vehicles",
    }
    for mod, kind in expect.items():
        src = inspect.getsource(__import__(mod, fromlist=["_"]))
        assert "make_save_open_buttons" in src, f"boutons absents : {mod}"
        assert f'kind="{kind}"' in src, f"kind {kind} manquant : {mod}"
        assert "_btn_save_file" in src and "_btn_open_file" in src, mod

    # 3) i18n FR+EN des nouveaux textes.
    from core.i18n import _FR_TO_EN
    for k in ("📂  Ouvrir", "Rien à sauvegarder.", "{n} élément(s) chargé(s).",
              "Charger ce fichier ? Les éléments actuels seront remplacés."):
        assert k in _FR_TO_EN, f"i18n manquante : {k}"


@test
def panneau_scenario_aligne_jusqu_au_bord():
    """Panneau Scénario droit : les cartes/boutons vont jusqu'au bord (conteneurs
    de section sans retrait horizontal, alignés sur les en-têtes pleine largeur)
    et les descriptions passent à la ligne (word-wrap) au lieu d'être tronquées."""
    import inspect
    src = inspect.getsource(__import__("ui.page_scenario", fromlist=["_"]))
    # Cartes jusqu'au bord : conteneur de section sans marge HORIZONTALE (0 …, 0 …).
    # Marges verticales resserrées à 4 (retour Matthieu : trop d'espace) — l'alignement
    # au bord (horizontal = 0) reste l'invariant.
    assert "lay.setContentsMargins(0, 4, 0, 4)" in src, "sections non alignées au bord"
    assert "b_lay.setContentsMargins(0, 8, 0, 12)" in src, "zone basse non alignée"
    assert "ga_lay.setContentsMargins(0, 10, 0, 12)" in src, "« Tout générer » non aligné"
    # Descriptions sur 2 lignes + hauteur de bouton suffisante.
    assert "sub_lbl.setWordWrap(True)" in src, "descriptions encore tronquées (pas de word-wrap)"
    assert "else 58)" in src, "hauteur de bouton non augmentée pour 2 lignes (58 par défaut)"
    # Bouton « Générer le storyboard » MIS EN AVANT (cadre vert, façon « Tout générer »).
    assert 'self._on_storyboard, color=CP["green"]' in src, "« Générer le storyboard » pas mis en avant (cadre coloré)"
    # Réorg 2026-07-06 : « Écriture assistée par IA » scindée en « Scénario »
    # (Analyse + Co-écriture) et « Finalisation » (Mise en page + Co-écriture des plans).
    assert '_make_toggle("📖  Scénario"' in src, "section Scénario (ex-IA) absente"
    assert '_make_toggle("🎯  Finalisation"' in src, "section Finalisation absente"
    assert '"Co-écriture des plans"' in src and "def _on_plan_coedit" in src, \
        "bouton/handler Co-écriture des plans absent (Cinéma)"
    # Ordre du panneau : Scénario avant Finalisation avant Générer.
    assert src.index("(tog_scen,") < src.index("(tog_final,") < src.index("(tog_gen,"), \
        "ordre du panneau droit incorrect (Scénario, Finalisation, …, Générer)"


@test
def coecriture_des_plans_cinema():
    """Finalisation Cinéma : parseur de plans « P01 | … » + fenêtre de co-écriture
    plan par plan (chirurgical), worker/dialog partagés calibrés « cinema »."""
    import core.plan_layout as pl
    cine = ("—— SÉQUENCE 1 ——\n\nP01 | Plan large | Fixe | Face | ~6s\nEXT. RUE — NUIT\nA.\n"
            "→ SEEDANCE: a.\n\nP02 | Gros plan | Fixe | 3/4 | ~5s\nINT. — NUIT\nB.\n→ SEEDANCE: b.\n")
    plans = pl.split_plans(cine)
    assert len(plans) == 2, "parseur Cinéma : 2 plans attendus"
    out = pl.replace_plan(cine, 0, "P01 | Insert | Fixe | Face | ~4s\nX")
    assert ("P02 | Gros plan" in out and "SÉQUENCE 1" in out
            and "→ SEEDANCE: a." not in out), \
        "replace_plan chirurgical (plan 2 + en-tête conservés, plan 0 remplacé)"
    from ui.dialog_plan_coedit import PlanCoEditDialog
    from api.plan_coedit import PlanCoEditWorker, _plan_coedit_system
    _syscine = _plan_coedit_system("cinema")
    assert "P<NN> |" in _syscine, "format Cinéma non calibré dans le prompt"
    # Le plan réécrit reste dans la LANGUE DE TRAVAIL (français par défaut) —
    # la traduction vers l'anglais est faite à l'ENVOI aux moteurs.
    assert "sensoriel, en français." in _syscine, "co-écriture Cinéma en langue de travail (fr)"
    dlg = PlanCoEditDialog(None, cine, edition="cinema")
    assert not dlg.was_applied() and dlg.result_layout() == cine
    # Réordonner (glisser-déposer) / ajouter / dupliquer / supprimer + renum P0N (Cinéma).
    _re = pl.reorder(cine, [1, 0])
    _lbls = [p["label"] for p in pl.split_plans(_re)]
    assert _lbls[0].startswith("P01 | Gros plan") and _lbls[1].startswith("P02 | Plan large"), "reorder + renum P0N"
    _add = pl.add_plan(cine, 0, "cinema")
    assert pl.plan_count(_add) == 3 and "P02 | Plan moyen" in _add, "add gabarit Cinéma + renum"
    assert pl.plan_count(pl.duplicate_plan(cine, 0)) == 3, "dup Cinéma"
    assert pl.plan_count(pl.delete_plan(cine, 0)) == 1, "delete Cinéma"
    for _m in ("_on_plans_reordered", "_plan_context_menu", "_duplicate_plan", "_delete_plan_at",
               "_add_plan", "_on_apply_all", "_commit_current_preview", "_has_pending"):
        assert hasattr(dlg, _m), f"handler {_m} absent du dialogue co-écriture Cinéma"
    # « Appliquer les modifications » : applique TOUT (édits + réordos + ajouts) en une
    # fois ; le structurel reste en état de TRAVAIL jusqu'au clic (2026-07-07).
    assert "Appliquer les modifications" in dlg._btn_apply.text(), "bouton non renommé (Cinéma)"
    dlg._duplicate_plan(0)
    assert not dlg.was_applied() and dlg._has_pending(), "Cinéma : structurel = travail, pas encore appliqué"
    dlg._on_apply_all()
    assert dlg.was_applied() and pl.plan_count(dlg.result_layout()) == 3, \
        "Cinéma : « Appliquer les modifications » valide + renumérote"

    # ── Anti-perte + auto-save + undo + le chat crée un vrai plan (2026-07-07) ──
    import inspect as _inspect
    assert hasattr(type(dlg), "layout_committed"), "signal auto-save layout_committed absent"
    for _m in ("_commit_layout", "_ensure_plan_header", "_undo", "_redo", "_on_preview_edited"):
        assert hasattr(dlg, _m), f"co-écriture : méthode anti-perte {_m} absente"
    # plan_layout : helpers en-tête / multi-plan
    assert pl.has_header("P01 | x | y | z | ~5s") and not pl.has_header("juste du texte")
    _mc = pl.replace_plan_multi(cine, 0, "P01 | A | Fixe | Face | ~5s\nX\n\nP02 | B | Fixe | Face | ~4s\nY")
    assert pl.plan_count(_mc) == 3 and "P03 | Gros plan" in _mc, "replace_plan_multi Cinéma : +1 + renum décale"
    assert pl.plan_count(pl.renumber_all(cine)) == 2, "renumber_all Cinéma conserve le nombre de plans"
    assert "CRÉER UN NOUVEAU PLAN" in _syscine, "prompt co-écriture : clause création de plan absente"
    # Dialogue — BUG A : une op structurelle NE jette PLUS la réécriture non committée.
    d2 = PlanCoEditDialog(None, cine, edition="cinema")
    _saved = []
    d2.layout_committed.connect(lambda t: _saved.append(t))
    d2._select_plan(0)
    d2._pending_plan = 0
    d2._on_plan_ready("P01 | Insert | Fixe | Face | ~4s\nINT. — NUIT\nMODIF_CINE.\n→ SEEDANCE: z.")
    d2._add_plan()
    assert "MODIF_CINE" in d2.result_layout() and _saved, \
        "Cinéma BUG A : op structurelle a jeté la réécriture / pas d'auto-save"
    # Undo revient à l'état d'avant l'ajout.
    _c = pl.plan_count(d2._layout); d2._undo()
    assert pl.plan_count(d2._layout) == _c - 1, "Cinéma : Ctrl+Z n'annule pas l'ajout"
    # Le chat crée un VRAI nouveau plan (multi-bloc) + renumérote.
    d3 = PlanCoEditDialog(None, cine, edition="cinema"); d3._select_plan(0); d3._pending_plan = 0
    d3._on_plan_ready("P01 | A | Fixe | Face | ~5s\nX\nA2\n→ SEEDANCE: a.\n\n"
                      "P02 | NEW | Fixe | Face | ~3s\nY\nnouveau\n→ SEEDANCE: n.")
    assert pl.plan_count(d3.result_layout()) == 3, "Cinéma : le chat ne crée pas de nouveau plan (multi)"
    # Parent : auto-save branché AVANT exec + slot silencieux.
    _psrc = _inspect.getsource(__import__("ui.page_scenario", fromlist=["_"]))
    assert "layout_committed.connect" in _psrc and "_on_plan_coedit_autosave" in _psrc, \
        "Cinéma : auto-save de la co-écriture non branché sur la page"
    # ── Plus d'images de référence (12) + cap UI == cap worker + ruban scrollable ──
    from api.plan_coedit import _MAX_REF_IMAGES as _MRI
    from ui.dialog_plan_coedit import _MAX_REFS as _DLG_MRI
    assert _MRI >= 12 and _DLG_MRI == _MRI, "co-écriture : cap images < 12 ou UI≠worker"
    assert "self._refs[:4]" not in _inspect.getsource(__import__("api.plan_coedit", fromlist=["_"])), \
        "co-écriture worker : cap figé [:4] encore présent"
    assert "QScrollArea" in _inspect.getsource(__import__("ui.dialog_plan_coedit", fromlist=["_"])), \
        "co-écriture : ruban de références non scrollable"
    # ── Discuter (chat pur) vs Modifier le plan (applique) — façon Image IA (2026-07-07) ──
    _sd = _plan_coedit_system("cinema", discuss_only=True)
    assert "DISCUTES" in _sd and "RÉPONDS TOUJOURS EN DEUX BLOCS" not in _sd, \
        "co-écriture : le mode discussion doit être conversationnel (pas de bloc plan forcé)"
    assert "RÉPONDS TOUJOURS EN DEUX BLOCS" in _plan_coedit_system("cinema", discuss_only=False), \
        "co-écriture : le mode modification doit demander le bloc plan"
    assert "discuss_only" in _inspect.signature(PlanCoEditWorker.__init__).parameters, \
        "worker co-écriture : param discuss_only absent"
    for _m in ("_btn_modify", "_on_modify_plan", "_launch"):
        assert hasattr(d3, _m), f"co-écriture : {_m} absent (bouton « Modifier le plan »)"
    assert "Modifier le plan" in d3._btn_modify.text(), "bouton « Modifier le plan » absent"
    # ── « Tous les plans » : correctif global (Cinéma, 2026-07-07) ──
    assert "CORRECTIF GLOBAL" in _plan_coedit_system("cinema", discuss_only=False, all_plans=True), \
        "system Cinéma : mode correctif global absent"
    for _m in ("_btn_all", "_on_toggle_all"):
        assert hasattr(d3, _m), f"co-écriture Cinéma : {_m} absent (Tous les plans)"
    d3._btn_all.setChecked(True)
    assert d3._all_mode and "Modifier tous les plans" in d3._btn_modify.text(), "activation « Tous les plans » KO (Cinéma)"
    # ⚠ ANTI-PERTE (bug 12/29 du 2026-07-08) : un correctif global qui renvoie MOINS de
    # plans que l'original est REJETÉ — aucun plan n'est perdu, on reste en mode « tous ».
    _n_avant = pl.plan_count(d3._layout)
    d3._pending_all = True
    d3._on_plan_ready("P01 | Tronqué | Fixe | Face | ~5s\nX\nZ2")   # 1 plan << _n_avant
    assert d3._all_mode and pl.plan_count(d3._layout) == _n_avant and "Z2" not in d3.result_layout(), \
        "correctif global tronqué : DOIT être rejeté sans rien perdre (Cinéma)"
    # Correctif complet (au moins autant de plans qu'à l'origine) → appliqué.
    _full = "\n\n".join(f"P0{i + 1} | Corr{i} | Fixe | Face | ~5s\nX{i}\nCORR{i}"
                        for i in range(_n_avant))
    d3._pending_all = True
    d3._on_plan_ready(_full)
    assert (not d3._all_mode and "CORR0" in d3.result_layout()
            and pl.plan_count(d3.result_layout()) == _n_avant), \
        "correctif global complet Cinéma : mise en page non appliquée"
    # Worker : correctif global PAR LOTS — lots tronqués par le modèle → fusion défensive,
    # jamais moins de plans qu'à l'origine (sinon échec explicite, aucune application).
    assert hasattr(PlanCoEditWorker, "_run_all_batched") and hasattr(PlanCoEditWorker, "progress"), \
        "worker : batching correctif global absent (_run_all_batched / progress)"
    _L12 = "\n\n".join(f"P{i:02d} | T{i} | Fixe | Face | ~5s\nX{i}\nB{i}" for i in range(1, 13))
    _wc = PlanCoEditWorker(layout_text=_L12, plan_text="", plan_label="", history=[],
                           user_message="corrige", edition="cinema", mode="cinema", all_plans=True)
    _rc = {}
    _wc.plan_ready.connect(lambda p: _rc.__setitem__("plan", p))
    _wc.failed.connect(lambda e: _rc.__setitem__("fail", e))
    def _tc(system, messages, **kw):
        _b = pl.split_plans(messages[-1]["content"])
        return "\n\n".join(x["text"] for x in _b[:2])   # ne renvoie que 2 plans / lot
    _wc._run_all_batched(_tc)
    assert "fail" not in _rc and pl.plan_count(_rc["plan"]) == 12, \
        "worker correctif global Cinéma : lots tronqués → PERTE (doit tout conserver)"
    # Sauvegarder / Ouvrir la co-écriture (sauvegarde de secours avant d'appliquer).
    for _m in ("_btn_save_file", "_btn_open_file", "_on_save_file", "_on_open_file", "_on_progress"):
        assert hasattr(d3, _m), f"co-écriture : {_m} absent (Sauvegarder/Ouvrir)"


@test
def refs_inspiration_completent_le_prompt_sans_alterer_keyframes():
    """Images de RÉFÉRENCE ajoutées + mode i2v (keyframes verrouillées, ex. mapping) :
    l'endpoint image-to-video n'accepte pas d'images de référence en plus, et on ne
    doit JAMAIS altérer l'image de départ/fin. real.py décrit alors l'inspiration en
    TEXTE (Claude Vision) et l'AJOUTE au prompt — jamais aux keyframes (2026-07-07)."""
    import inspect
    import api.real as _real
    # Helper vision offline-safe : pas de clé / mauvais chemins → "" (jamais bloquant).
    assert _real._analyze_reference_refs([], "") == "", "vision refs : vide sûr sans image"
    assert _real._analyze_reference_refs(["/pas/un/fichier.png"], "") == "", "vision refs : chemin invalide sûr"
    _src = inspect.getsource(_real.run_real)
    # En i2v, les refs rôle « reference » sont analysées puis AJOUTÉES au prompt…
    assert 'r == "reference"' in _src and "_analyze_reference_refs(" in _src, \
        "i2v : refs d'inspiration non branchées sur le prompt"
    # …avec la consigne explicite de ne pas toucher aux images de départ/fin.
    assert "do NOT alter the first or last frame" in _src, \
        "i2v : consigne de préservation des keyframes absente"
    # Les keyframes partent bien par image_url (départ) / end_image_url (fin).
    assert 'args["image_url"]' in _src and 'args["end_image_url"]' in _src, \
        "keyframes départ/fin non transmises comme images verrouillées"


@test
def studio_ia_onglets_style_conducteur():
    """Onglets Studio IA Cinéma façon Conducteur (2026-07-06) : barre fond bg0 +
    filet haut/bas, séparateurs de groupe conservés ; bouton « Envoyer à Claude »
    dans le chat Image IA (studio_images)."""
    import inspect
    sw = inspect.getsource(__import__("ui.seedance_widget", fromlist=["_"]))
    assert "QTabBar{{background:{C['bg0']};border:none;}}" in sw, \
        "barre d'onglets Studio IA Cinéma : fond noir + AUCUNE bordure (sinon ligne doublée/tronquée)"
    assert "QTabWidget::pane{{border:none;border-top:1px solid" in sw, \
        "filet pleine largeur sous la barre (bord haut du pane, façon Conducteur)"
    assert "_GroupedTabBar" in sw and "set_group_ends({3, 5, 6})" in sw, \
        "séparateurs de groupe Cinéma cassés"
    with open("studio_images/window.py", encoding="utf-8") as f:
        win = f.read()
    assert "Envoyer à Claude" in win and "self._send_chat" in win, \
        "bouton « Envoyer à Claude » absent du chat Image IA"


@test
def fleches_dialogue_fichier_en_blanc():
    """Flèches de navigation (précédent/parent/vue) du dialogue de fichiers non-natif
    recolorées en clair — invisibles sinon sur fond sombre (retour Matthieu 2026-07-06)."""
    import inspect
    import ui.file_dialogs as fd
    src = inspect.getsource(fd)
    assert "def _whiten_nav_icons" in src and "CompositionMode_SourceIn" in src, \
        "recolorisation des icônes du dialogue de fichiers absente"
    assert "_whiten_nav_icons(dlg)" in src, "_whiten_nav_icons non appelé dans apply_thumbnails"
    from PyQt6.QtWidgets import QFileDialog
    dlg = QFileDialog()
    dlg.setNameFilter("Images (*.png *.jpg)")
    fd.apply_thumbnails(dlg)     # ne doit pas planter + recolore les icônes
    dlg.deleteLater()


@test
def enrichissement_refs_chirurgical():
    """Enrichissement « Références visuelles » CHIRURGICAL (2026-07-06) : le worker
    renvoie des édits {find, replace} (moins de tokens) au lieu de tout réécrire ;
    core.text_edits les applique en gardant le reste MOT POUR MOT."""
    import inspect
    from api.screenplay import EnrichScenarioWithRefsWorker
    sysp = EnrichScenarioWithRefsWorker._SYSTEM
    assert '"find"' in sysp and '"replace"' in sysp and '"edits"' in sysp, \
        "prompt enrichissement Cinéma : format édits JSON absent"
    assert "parse_edits" in inspect.getsource(EnrichScenarioWithRefsWorker.run), \
        "run() ne parse pas les édits"
    # Parseur + application chirurgicale (core partagé).
    import core.text_edits as tx
    orig = "ACTE 1\nUne rue vide sous la pluie.\nUn homme attend.\nACTE 2\nFin."
    edits = tx.parse_edits(
        '{"edits":[{"find":"Une rue vide sous la pluie.",'
        '"replace":"Une rue néon, reflets cyan, sous la pluie.","summary":"palette"}]}')
    assert len(edits) == 1, "parseur d'édits"
    new, applied, missed = tx.apply_find_replace_edits(orig, edits)
    assert "néon, reflets cyan" in new and "Un homme attend." in new and "ACTE 2" in new, \
        "application chirurgicale : passage remplacé, reste intact"
    assert len(applied) == 1 and not missed
    # UI : application via apply_find_replace_edits (plus de remplacement total streamé).
    from ui.page_scenario import PageScenario
    _refsrc = inspect.getsource(PageScenario._open_refs_window)
    assert "apply_find_replace_edits" in _refsrc, "UI Cinéma n'applique pas les édits chirurgicaux"
    # Le bouton « Enrichir » ne doit JAMAIS être masqué au clic — seulement grisé
    # pendant le traitement, puis réactivé (retour Matthieu : il disparaissait).
    assert "btn_enrich.setVisible(False)" not in _refsrc, \
        "bouton « Enrichir » masqué au clic (il doit rester visible, juste grisé)"


@test
def refs_indicateur_deja_enrichi():
    """Indicateur « scénario déjà enrichi » (2026-07-06) : flag en mémoire (refs Cinéma
    non persistées), remis à zéro à chaque analyse, petit signe sur le bouton Enrichir."""
    import inspect
    from ui.page_scenario import PageScenario
    p = PageScenario()
    assert hasattr(p, "_ref_enriched") and p._ref_enriched is False, "flag initialisé à False"
    rw = inspect.getsource(PageScenario._open_refs_window)
    assert "self._ref_enriched = True" in rw, "flag posé à l'application"
    assert "self._ref_enriched = False" in rw, "flag remis à zéro (nouvelle analyse)"
    assert "déjà enrichi" in rw, "petit signe « déjà enrichi » sur le bouton"


@test
def plan_architecte_cale_sur_ensemble():
    """7 vues : le plan d'architecte est généré par ÉDITION NB2 à partir de l'image
    d'ensemble (donc calé dessus), avec repli texte robuste ; ensemble + plan ont un
    retry (plus de « 1 décor + plan ») ; les 6 faces référencent le plan d'architecte
    pour le raccord spatial. Worker partagé → Scénario, Variations et dialog Décor."""
    import inspect
    nb = inspect.getsource(__import__("api.nano_banana", fromlist=["_"]))
    assert "fp_anchor" in nb and "_gen_edit(fp_anchor, ov_ref" in nb, \
        "plan d'architecte non calé sur le plan d'ensemble (devrait être édité depuis l'ensemble)"
    assert "ov_ref = [_dataurl(ov_path)]" in nb, "le plan n'utilise pas l'ensemble comme référence"
    assert "_gen_text_robust" in nb and "_gen_text_robust(full_ov" in nb, \
        "ensemble/plan sans repli robuste (retry)"
    assert "TOP-DOWN architectural floor plan giving the exact layout" in nb, \
        "les faces ne référencent pas explicitement le plan d'architecte"
    # Les deux flux assignent bien le plan partagé (is_floor_plan) aux décors.
    for mod, who in (("ui.dialog_extract_generate", "scénario"),
                     ("ui.dialog_room_variations", "variations")):
        src = inspect.getsource(__import__(mod, fromlist=["_"]))
        assert "is_floor_plan" in src and "floor_plan" in src, f"plan non assigné ({who})"


@test
def analyse_musicale_scenario_cinema():
    """Scénario Cinéma : section « Musiques du set » + analyse BPM/drops (moteur
    librosa PARTAGÉ avec le Live), timeline injectée dans la génération du
    storyboard (clip), persistance des morceaux, et librosa embarqué au build."""
    import inspect, os as _os
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from ui.page_scenario import PageScenario
    p = PageScenario()
    for m in ("_refresh_music_display", "_make_music_chip", "_on_add_music",
              "_on_analyze_music", "_open_music_analysis_window", "_edit_bpm",
              "_remove_music", "_text_with_music"):
        assert hasattr(p, m), "méthode musique manquante : " + m
    assert hasattr(p, "_music_hbox") and hasattr(p, "_btn_analyze_music")
    assert hasattr(p, "_choose_music_mode"), "popup de choix film/clip absent"
    # Renommage Cinéma : « Musique du film » (et plus « Musiques du set »).
    src = inspect.getsource(PageScenario)
    assert "♫  Musique du film" in src, "section non renommée en « Musique du film »"
    # Timeline injectée selon le MODE choisi avant l'analyse.
    p._music_tracks = [{"name": "t", "bpm": 128, "duration": 200, "energy": "▁█", "drops": [8.0]}]
    p._music_mode = "clip"
    tw = p._text_with_music()
    assert "MUSIQUE DU CLIP" in tw and "128 BPM" in tw, "mode clip non injecté"
    p._music_mode = "film"
    tf = p._text_with_music()
    assert "MUSIQUE DU FILM" in tf and "MOMENTS CLÉS" in tf, "mode film non injecté"
    # Non-régression Live : build_set_timeline sans mode = comportement d'origine.
    from core.music_analysis import build_set_timeline
    live_tl = build_set_timeline([{"name": "x", "bpm": 120, "duration": 100, "drops": []}])
    assert "TIMELINE MUSICALE DU SET" in live_tl and "Resolume" in live_tl, "Live altéré"
    # Persistance round-trip morceaux + mode.
    p._open_scenario({"title": "T", "raw_content": "x",
                      "music_tracks": [{"name": "a", "bpm": 90}], "music_mode": "film"})
    assert p._music_tracks and p._music_tracks[0]["bpm"] == 90, "music_tracks non rechargé"
    assert p._music_mode == "film", "music_mode non rechargé"
    # Les DEUX chemins de génération du storyboard injectent la timeline.
    src = inspect.getsource(PageScenario)
    assert src.count("self._text_with_music()") >= 2, "timeline non injectée dans la génération"
    # Build : librosa déclaré, numpy/scipy retirés des excludes.
    with open(_os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "pandora.spec"),
              encoding="utf-8") as f:
        spec = f.read()
    assert '"librosa"' in spec, "librosa non déclaré au build Cinéma"
    exc = spec.split("excludes=[")[1].split("]")[0]
    assert '"numpy"' not in exc and '"scipy"' not in exc, "numpy/scipy encore exclus du build"


@test
def sync_storyboard_vers_mise_en_scene():
    """Mise en scène : nouvelle synchro INVERSE storyboard → mise en scène. Après un
    « Tout supprimer » (record vidé, _actors_seeded verrouillé, plan « __none__ »),
    elle FORCE le re-semis (acteurs + caméra depuis le storyboard) et remet le plan
    de décor en Auto → récupération de la mise en scène. Les deux sens coexistent."""
    import inspect
    from PyQt6.QtWidgets import QApplication, QMessageBox
    QApplication.instance() or QApplication([])
    import core.staging as stg
    # Plan construit en direct (on isole du storyboard partagé du harnais).
    shot = {"id": "sync_inv_shot", "number": "1", "scene_title": "T",
            "character_names": ["Alice", "Bob"], "camera_axis": "Latéral 90°"}
    sid = shot["id"]
    # Simule « Tout supprimer » : record vidé + semis verrouillé + plan désactivé.
    stg.save(sid, {"plan_image": "", "camera": {}, "actors": [], "props": [],
                   "lights": [], "_actors_seeded": True, "plan_decor_id": "__none__"})
    from ui.page_staging import PageStaging
    p = PageStaging()
    p._mode = "staging"
    p._shots = [shot]
    _exec, _info = QMessageBox.exec, QMessageBox.information
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Yes
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    try:
        p._sync_from_storyboard()
    finally:
        QMessageBox.exec, QMessageBox.information = _exec, _info
    rec = stg.get(sid)
    assert [a["name"] for a in rec["actors"]] == ["Alice", "Bob"], rec["actors"]
    assert rec["camera"].get("angle") == 90.0, rec["camera"]   # axe Latéral 90°
    assert rec.get("plan_decor_id") == "", "plan de décor non remis en Auto"
    src = inspect.getsource(PageStaging)
    assert ("_sync_from_storyboard" in src and "_sync_to_storyboard" in src), "les deux sens absents"
    assert "Synchroniser le storyboard → mise en scène" in src, "entrée de menu inverse absente"


@test
def storyboard_hauteur_libelle_moods():
    """Storyboard Cinéma : colonne Hauteur (après Dist.), libellé couleur en FOND de
    la cellule Séquence (plus de bande gauche), boutons Sauvegarder/Ouvrir déplacés
    à droite (près de « Ajouter un plan »), message moods honnête (succès/échecs) +
    garde-fou clé fal.ai. camera_height a un défaut côté core."""
    import inspect
    import ui.page_storyboard as P
    assert P._COLS[19][0] == "Hauteur", "colonne Hauteur absente"
    assert P._DEFAULT_COL_ORDER.index(19) == P._DEFAULT_COL_ORDER.index(9) + 1, \
        "Hauteur n'est pas juste après Dist."
    src = inspect.getsource(P)
    assert "background:{_lc or seq_bg}" in src, "libellé couleur pas en fond de cellule Séquence"
    assert "border-left:4px solid {_lc}" not in src, "la bande couleur à gauche subsiste"
    assert "cells[19] = hgt_w" in src, "cellule Hauteur non assemblée"
    assert ("self._btn_save_sb_file" in src and "self._btn_open_sb_file" in src), "boutons fichier absents"
    assert "lay.addWidget(self._btn_save_sb_file)" not in src, "Sauvegarder ne doit plus être collé à droite"
    assert "insertSpacing" in src, "espace/barre de séparation avant Sauvegarder/Ouvrir manquant"
    assert ("Aucun mood généré" in src and "_mood_ok" in src and "_mood_fail" in src), \
        "message moods non fiabilisé"
    assert "Configure ta clé fal.ai dans Paramètres pour générer les moods." in src, \
        "garde-fou clé fal.ai absent"
    assert P._contrast_text("#ffc040") == "#07080f", "contraste texte incorrect"
    import core.storyboard as _sb
    assert 'data.setdefault("camera_height"' in inspect.getsource(_sb), "camera_height sans défaut"


@test
def sync_reecrit_scenario_projet_vierge():
    """Storyboard → « Réécrire le scénario depuis le storyboard » : dans un projet
    vierge (storyboard importé, aucun scénario), le texte reconstruit devient le
    CONTENU COURANT (visible dans l'éditeur) et pas seulement une version cachée ;
    si un scénario existe déjà, son contenu n'est jamais écrasé (nouvelle version)."""
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import core.scenario as scn
    import core.context as ctx
    from ui.dialog_storyboard_sync import StoryboardSyncDialog
    dlg = StoryboardSyncDialog.__new__(StoryboardSyncDialog)   # sans __init__ (pas de worker)
    _saved = ctx.get_project_id()
    try:
        ctx.set_project_id("sync_scn_vierge_test")
        assert scn.list_scenarios() == [], "projet de test non vierge"
        dlg._save_scenario_version("RECONSTRUIT depuis le storyboard")
        scs = scn.list_scenarios()
        assert scs and "RECONSTRUIT" in (scs[0].get("raw_content") or ""), \
            "scénario reconstruit absent du contenu courant"
        # Scénario existant rempli → on NE l'écrase PAS : fiche SÉPARÉE « reconstruit ».
        scn.save_scenario({"id": scs[0]["id"], "project_id": "sync_scn_vierge_test",
                           "raw_content": "ORIGINAL", "formatted_content": "ORIGINAL"})
        saved = dlg._save_scenario_version("AUTRE RECONSTRUCTION")
        assert scn.get_scenario(scs[0]["id"])["raw_content"] == "ORIGINAL", "scénario existant écrasé"
        assert "AUTRE RECONSTRUCTION" in (saved.get("raw_content") or ""), "fiche reconstruite vide"
        assert any("AUTRE RECONSTRUCTION" in (s.get("raw_content") or "")
                   for s in scn.list_scenarios()), "fiche reconstruite absente de la liste"
    finally:
        ctx.set_project_id(_saved)


@test
def editeur_scenario_recharge_apres_sync():
    """« Rien dans Scénario après réécriture » : un éditeur Scénario VIDE déjà ouvert
    se recharge depuis le disque (showEvent) pour afficher le scénario reconstruit par
    la synchro Storyboard — sans jamais écraser une saisie en cours."""
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import core.context as ctx
    from ui.page_scenario import PageScenario
    from ui.dialog_storyboard_sync import StoryboardSyncDialog
    _saved = ctx.get_project_id()
    try:
        ctx.set_project_id("editor_reload_test")
        pg = PageScenario()
        # Cas réel : éditeur avec un TITRE « Scénario » mais SANS contenu (le titre ne
        # doit PAS empêcher le rechargement — c'était le bug).
        pg._open_scenario({"title": "Scénario"})
        assert pg._stack.currentIndex() == 1, "éditeur non ouvert"
        assert pg._title_edit.text().strip() == "Scénario" and not pg._editor_text.toPlainText().strip()
        StoryboardSyncDialog.__new__(StoryboardSyncDialog)._save_scenario_version(
            "INT. SALLE — NUIT\nLe scénario reconstruit depuis le storyboard.")
        pg._reload_if_empty_editor()          # ce que déclenche showEvent
        assert "reconstruit" in pg._editor_text.toPlainText(), "éditeur (titre mais vide) non rechargé"
        # Saisie en cours JAMAIS écrasée (du TEXTE présent → pas de rechargement).
        pg._open_scenario({"id": "keep", "title": "X", "raw_content": "TRAVAIL EN COURS"})
        pg._reload_if_empty_editor()
        assert pg._editor_text.toPlainText() == "TRAVAIL EN COURS", "saisie en cours écrasée"
    finally:
        ctx.set_project_id(_saved)


@test
def variations_prompt_francais():
    """Variations de décor : le prompt (stocké en anglais) s'affiche en FRANÇAIS
    (traduction Haiku en tâche de fond) ; la génération le retraduit en anglais. On
    vérifie la logique de remplacement + l'anti-clobber, sans appel réseau."""
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from core.lang import translate_to_french
    assert callable(translate_to_french), "translate_to_french absent"
    import core.i18n as i18n
    from ui.dialog_room_variations import RoomVariationsDialog, _PromptTranslateWorker
    assert _PromptTranslateWorker is not None
    _lang = i18n.get_lang()
    try:
        i18n.set_lang("en")   # app EN → pas de traduction auto à l'ouverture (zéro réseau)
        decors = [{"id": "o", "room_group": "SAM", "room_view": "Ensemble",
                   "prompt": "A dark wooden dining room"}]
        dlg = RoomVariationsDialog(None, "SAM", decors)
        assert dlg._prompt.toPlainText() == "A dark wooden dining room"
        # Remplacement quand le champ n'a pas été modifié.
        dlg._orig_en = dlg._prompt.toPlainText().strip()
        dlg._on_prompt_translated("Une salle à manger sombre en bois")
        assert dlg._prompt.toPlainText() == "Une salle à manger sombre en bois", \
            "prompt non remplacé par la version française"
        # Anti-clobber : saisie en cours jamais écrasée par la traduction tardive.
        dlg._prompt.setPlainText("Ma variation à moi")
        dlg._on_prompt_translated("Autre traduction")
        assert dlg._prompt.toPlainText() == "Ma variation à moi", "saisie écrasée"
    finally:
        i18n.set_lang(_lang)


@test
def moods_nb2_cadrage_et_lifecycle():
    """Moods NB2 : les références (persos + décor, souvent un plan d'ensemble) servent
    à la COHÉRENCE, pas au cadrage → consigne imposant le plan prévu, depuis l'intérieur
    du décor, persos placés dedans, sans recopier le plan d'ensemble. + worker batch
    PARQUÉ (abandon_thread) au lieu de « = None » à chaud (anti-segfault)."""
    import inspect
    import api.apercu as ap_mod
    d = ap_mod._MOOD_REF_DIRECTIVE   # valeur runtime (concaténée)
    assert "FROM INSIDE this room" in d, "cadrage : « depuis l'intérieur du décor » manquant"
    assert "Do NOT reproduce" in d and "overview" in d, "anti-recopie du plan d'ensemble manquant"
    assert "place the character" in d, "placement des personnages dans le décor manquant"
    ap = inspect.getsource(ap_mod)
    assert ap.count("_MOOD_REF_DIRECTIVE") >= 2, "consigne de cadrage NB2 non injectée à l'édition"
    sb = inspect.getsource(__import__("ui.page_storyboard", fromlist=["_"]))
    assert "abandon_thread(w)" in sb, "worker mood non parqué (risque de segfault)"
    # Upload des réfs robuste : pas de fal_client.upload_file brut dans le chemin NB2
    # (échoue sur chemins non-ASCII + erreur « Invalid storage type »). Fallback data-URL.
    nb2_src = inspect.getsource(ap_mod.run_generation_nb2)
    assert "upload_file" not in nb2_src, "moods NB2 : upload_file brut (fragile non-ASCII/stockage)"
    assert "_upload_ref_robust" in nb2_src, "moods NB2 : upload robuste non utilisé"
    rob = inspect.getsource(ap_mod._upload_ref_robust)
    assert "data:" in rob and "b64encode" in rob, "fallback data-URL stockage manquant"


@test
def mood_reference_dans_rendu_audio():
    """Studio IA Cinéma → RENDU & AUDIO : toggle « Se référer au mood ». Activé, il
    envoie le mood ACTIF du plan comme image de référence Seedance (rôle « mood »)
    pour une cohésion exacte. Mood actif = paths[active_idx]. Le rôle « mood » porte
    une consigne @ImageN forte côté api/real.py."""
    import inspect
    t2v = inspect.getsource(__import__("ui.tab_t2v", fromlist=["_"]))
    # Toggle présent dans RENDU & AUDIO
    assert '"Se référer au mood"' in t2v, "toggle « Se référer au mood » absent"
    assert "self._mood_ref_cb" in t2v, "checkbox mood ref absente"
    # Injection : le mood part comme réf avec le rôle « mood »
    assert 'ref_image_roles + ["mood"]' in t2v, "rôle « mood » non ajouté aux réfs"
    assert "self._active_mood_path" in t2v, "chemin du mood actif non suivi"
    # Mood ACTIF = active_idx (pas juste le premier)
    assert 'active_idx' in t2v and "_active_mood_path = " in t2v, "active_idx non pris en compte"
    # Gardes : Seedance uniquement + toggle coché + fichier existant
    assert "_mood_ref_cb.isChecked()" in t2v
    # Consigne @ImageN « mood » côté API réelle (cohésion composition/lumière/couleur)
    real = inspect.getsource(__import__("api.real", fromlist=["_"]))
    assert '_role == "mood"' in real, "branche rôle « mood » absente d'api/real.py"
    assert "MOOD / LOOK REFERENCE" in real, "consigne cohésion mood absente"
    # i18n FR→EN du libellé
    import core.i18n as i18n
    assert "Se référer au mood" in i18n._FR_TO_EN


@test
def lipsync_rendu_audio_storyboard():
    """Synchro labiale dans RENDU & AUDIO (Générer depuis le storyboard) : moteurs
    fal.ai sélectionnables (défaut Sync 2 Pro), audio = TTS auto du dialogue OU
    fichier attaché par plan, worker dédié parqué (anti-segfault)."""
    import inspect
    # ── Catalogue de moteurs (api/lipsync) ──────────────────────────────────
    import api.lipsync as ls
    assert ls.LIPSYNC_DEFAULT == "sync2pro"
    assert ls.LIPSYNC_ENGINE_ORDER[0] == "sync2pro"
    assert ls.lipsync_endpoint("sync2pro") == "fal-ai/sync-lipsync/v2/pro"
    assert ls.lipsync_endpoint("sync3") == "fal-ai/sync-lipsync/v3"
    assert ls.lipsync_endpoint("zzz") == "fal-ai/sync-lipsync/v2/pro"  # repli
    assert set(ls.LIPSYNC_ENGINES) == {"sync2pro", "sync3", "sync2", "latentsync"}
    assert ls.LipSyncWorker is ls.LatentSyncWorker  # rétro-compat « Modifier depuis DaVinci »
    # Upload audio robuste (non-ASCII + fallback data-URL) présent
    rob = inspect.getsource(ls._upload_audio_robust)
    assert "b64encode" in rob and "data:" in rob

    # ── Extraction de dialogue (core/dialogue) ──────────────────────────────
    from core.dialogue import extract_shot_dialogue
    assert extract_shot_dialogue({"seedance_prompt": 'Il dit «Bonjour».'}) == "Bonjour"
    assert extract_shot_dialogue({"dialogue": "Salut"}) == "Salut"
    assert extract_shot_dialogue({"seedance_prompt": "pas de dialogue"}) == ""

    # ── Worker par plan (api/shot_lipsync) ──────────────────────────────────
    import api.shot_lipsync as sl
    w = sl.ShotLipSyncWorker({"id": "s1", "lipsync_audio_path": "C:/x.wav"},
                             "http://v", "out", engine="sync3")
    assert w._audio_path == "C:/x.wav" and w._engine == "sync3"
    assert hasattr(w, "done") and hasattr(w, "failed") and hasattr(w, "progress")

    # ── UI tab_t2v : toggle + sélecteur + file lip-sync ─────────────────────
    t2v = inspect.getsource(__import__("ui.tab_t2v", fromlist=["_"]))
    assert '"Resynchroniser les lèvres (lip-sync)"' in t2v
    assert "self._lipsync_cb" in t2v and "self._lipsync_engine_combo" in t2v
    assert "_start_shot_lipsync" in t2v and "_advance_after_clip" in t2v
    assert "ShotLipSyncWorker" in t2v
    assert "abandon_thread" in t2v, "worker lip-sync non parqué (anti-segfault)"
    assert 'self._pending_advance' in t2v
    # Override manuel par plan (dialog_shot) + persistance
    ds = inspect.getsource(__import__("ui.dialog_shot", fromlist=["_"]))
    assert "self._lipsync_audio" in ds and '"lipsync_audio_path"' in ds
    # Schéma plan : champ persité
    import core.storyboard as sb
    assert 'lipsync_audio_path' in inspect.getsource(sb)
    # i18n
    import core.i18n as i18n
    assert "Resynchroniser les lèvres (lip-sync)" in i18n._FR_TO_EN
    assert "Moteur lip-sync" in i18n._FR_TO_EN


@test
def raccord_bar_jamais_fenetre_flottante():
    """La barre « Raccord automatique » est RETIRÉE de l'UI Cinéma : objet gardé SANS
    parent ni layout, uniquement pour _prev_shot (toggle I2V + get_i2v_frame). Régression :
    update_shot ne doit JAMAIS l'afficher — sinon une fenêtre flottante parasite s'ouvre
    pendant la génération en série (chaque plan appelle _on_shot_selected → update_shot)."""
    import inspect
    import ui.tab_t2v as M
    tab = M.TabT2V()
    bar = tab._continuity_bar
    assert bar.parent() is None, "barre sans parent → l'afficher = fenêtre flottante"
    # Chemin succès (plan courant AVEC plan précédent)
    bar.update_shot({"number": 2}, [{"number": 1, "decor_name": "X"}, {"number": 2}])
    assert bar._prev_shot is not None, "raccord I2V cassé (_prev_shot perdu)"
    assert not bar.isVisible(), "barre raccord visible → fenêtre flottante parasite"
    # Idem sans plan précédent (early-return) : reste cachée
    bar.update_shot({"number": 1}, [{"number": 1}])
    assert not bar.isVisible(), "barre raccord visible (early-return)"


@test
def detourage_personnage_envoye_a_seedance():
    """Quand on supprime le fond d'un portrait, c'est l'image DÉTOURÉE qui part vers
    Seedance — pas l'ancien fond. Deux causes corrigées :
      1. la planche 4 vues (sheet_path, AVEC fond) était préférée → on l'efface au
         détourage pour que image_path (détouré) serve de référence ;
      2. la mosaïque aplatissait l'alpha (.convert RGB) → le fond d'origine sous les
         pixels transparents réapparaissait → on compose désormais via le masque alpha."""
    import inspect, os, tempfile
    # ── 1. Détourage efface sheet_path ──────────────────────────────────────
    import ui.dialog_character as DC
    cls = next(c for n, c in vars(DC).items()
               if isinstance(c, type) and "Dialog" in n and hasattr(c, "_on_bg_removed"))
    assert 'self._sheet_path = ""' in inspect.getsource(cls._on_bg_removed), \
        "le détourage doit retirer la planche 4 vues comme référence"
    # ── 2. Mosaïque : alpha respecté (cutout → fond neutre, pas le fond d'origine) ─
    try:
        from PIL import Image
    except ImportError:
        return  # PIL absent : la mosaïque retombe sur les images brutes (ok)
    import core.mosaic as mo
    d = tempfile.mkdtemp(prefix="t_mos_")
    cut = os.path.join(d, "cut.png")
    Image.new("RGBA", (200, 200), (255, 0, 0, 0)).save(cut)  # rouge mais transparent
    out = os.path.join(d, "m.png")
    assert mo._composite([(cut, "Perso")], out), "composite mosaïque échoué"
    cx, cy = mo._CELL_W // 2, (mo._CELL_H - mo._LABEL_H) // 2
    r, g, b = Image.open(out).convert("RGB").getpixel((cx, cy))
    assert r < 60 and g < 60 and b < 70, f"fond d'origine réapparu sous l'alpha : {(r, g, b)}"
    # Source : compositing via masque alpha présent
    cs = inspect.getsource(mo._composite)
    assert "canvas.paste(img, (px, py), img)" in cs, "paste avec masque alpha manquant"
    # ── 3. Préférence rétroactive : un portrait détouré PRIME sur la planche ─────
    op_sheet = os.path.join(d, "sheet_op.png")
    Image.new("RGB", (200, 200), (0, 0, 255)).save(op_sheet)          # planche opaque
    transp = os.path.join(d, "cut2.png")
    Image.new("RGBA", (200, 200), (0, 255, 0, 0)).save(transp)        # portrait détouré
    # Détouré présent → on prend le détouré, pas la planche (fond d'origine)
    assert mo._pick_char_ref({"sheet_path": op_sheet, "image_path": transp}) == transp
    # Pas de détourage → planche (multi-vues) conservée
    op_port = os.path.join(d, "port_op.png")
    Image.new("RGB", (200, 200), (200, 200, 200)).save(op_port)
    assert mo._pick_char_ref({"sheet_path": op_sheet, "image_path": op_port}) == op_sheet


@test
def moods_plan_architecte_repere():
    """Moods NB2 : le plan d'architecte (vue de dessus) du décor est envoyé EN PLUS,
    en DERNIÈRE référence, avec une consigne dédiée (repère d'agencement de la pièce,
    pas une image à reproduire). Le dispatcher le récupère via floor_plan_for_shot."""
    import inspect, sys, types, os, tempfile
    import api.apercu as A
    # Consigne dédiée présente + cible « la dernière image »
    d = A._FLOOR_PLAN_DIRECTIVE
    assert "FLOOR PLAN" in d and "LAST reference image" in d
    assert "Do NOT" in d and ("geometry" in d or "layout" in d)
    # run_mood passe le plan d'architecte du décor
    rm = inspect.getsource(A.run_mood)
    assert "floor_plan_for_shot" in rm and "floor_plan=" in rm
    # Comportement : plan envoyé EN DERNIER + 2 consignes (stub fal_client)
    fake = types.ModuleType("fal_client")
    cap = {}
    fake.subscribe = lambda endpoint, arguments=None, **k: (
        cap.update(args=arguments) or {"images": [{"url": "http://o.png"}]})
    fake.upload = lambda data, content_type=None: "U" + str(len(data))
    sys.modules["fal_client"] = fake
    import requests
    _orig_get = requests.get
    requests.get = lambda url, timeout=120: types.SimpleNamespace(content=b"PNG")
    try:
        td = tempfile.mkdtemp(prefix="t_moodfp_")
        def _mk(n, sz):
            p = os.path.join(td, n); open(p, "wb").write(b"x" * sz); return p
        perso, decor, plan = _mk("p.png", 10), _mk("d.png", 20), _mk("fp.png", 30)
        A.run_generation_nb2("PR", td, "k", lambda m: None, [perso, decor], floor_plan=plan)
        urls = cap["args"]["image_urls"]
        assert urls[-1] == "U30", "le plan d'architecte doit être la DERNIÈRE référence"
        assert "FLOOR PLAN" in cap["args"]["prompt"], "consigne plan d'architecte absente"
        # Sans plan : pas de consigne plan
        cap.clear()
        A.run_generation_nb2("PR", td, "k", lambda m: None, [perso], floor_plan="")
        assert "FLOOR PLAN" not in cap["args"]["prompt"]
    finally:
        requests.get = _orig_get


@test
def moods_reference_images_inspiration():
    """Colonne « Référence » du storyboard → injectée au Mood comme INSPIRATION (2026-07-08).
    Cinéma/NB2 : les images de référence NE reçoivent PAS la consigne de cohérence
    (« même pièce / mêmes persos ») — sinon l'IA les recopierait — mais une consigne
    d'inspiration DÉDIÉE. run_mood les lit depuis shot['reference_images']."""
    import inspect, types, tempfile, os, sys
    import api.apercu as A
    assert "inspiration_refs" in inspect.signature(A.run_generation_nb2).parameters, \
        "run_generation_nb2 : param inspiration_refs absent"
    d = A._INSPIRATION_REF_DIRECTIVE
    assert "INSPIRATION" in d and "NOT" in d and ("copied" in d or "reproduced" in d), \
        "directive d'inspiration dédiée absente / mal formulée"
    rm = inspect.getsource(A.run_mood)
    assert 'shot.get("reference_images")' in rm and "inspiration_refs=_inspo" in rm, \
        "run_mood n'injecte pas reference_images en NB2"
    assert "inspiration_ref = _inspo[0]" in rm, "run_mood : repli inspiration Flux absent"
    fake = types.ModuleType("fal_client"); cap = {}
    fake.subscribe = lambda endpoint, arguments=None, **k: (
        cap.update(args=arguments) or {"images": [{"url": "http://o.png"}]})
    fake.upload = lambda data, content_type=None: "U" + str(len(data))
    sys.modules["fal_client"] = fake
    import requests
    _orig_get = requests.get
    requests.get = lambda url, timeout=120: types.SimpleNamespace(content=b"PNG")
    try:
        td = tempfile.mkdtemp(prefix="t_moodinsp_")
        def _mk(n, sz): p = os.path.join(td, n); open(p, "wb").write(b"x" * sz); return p
        insp, perso = _mk("i.png", 40), _mk("p.png", 10)
        # Inspiration SEULE : consigne inspiration présente, JAMAIS « même pièce »
        A.run_generation_nb2("PR", td, "k", lambda m: None, [], inspiration_refs=[insp])
        pr = cap["args"]["prompt"]
        assert "ARTISTIC INSPIRATION" in pr, "consigne inspiration absente"
        assert "the SAME room" not in pr, \
            "PIÈGE : consigne de cohérence appliquée à une image d'inspiration seule"
        assert cap["args"]["image_urls"] == ["U40"], "image d'inspiration non envoyée"
        # Cohérence + inspiration : préambule d'ordre + les DEUX consignes distinctes
        cap.clear()
        A.run_generation_nb2("PR", td, "k", lambda m: None, [perso], inspiration_refs=[insp])
        pr = cap["args"]["prompt"]
        assert "IMAGE ORDER" in pr and "the SAME room" in pr and "ARTISTIC INSPIRATION" in pr, \
            "mélange cohérence+inspiration : préambule/consignes manquants"
        assert cap["args"]["image_urls"] == ["U10", "U40"], "ordre cohérence puis inspiration"
    finally:
        requests.get = _orig_get


@test
def moods_fenetre_options():
    """Fenêtre « Générer les Moods » : options cochables (moteur NB2/Flux, réfs persos,
    réf décor, plan d'architecte). Les réfs ne concernent que NB2 (grisées en Flux) ;
    les options sont transmises au worker, et run_mood les applique."""
    import inspect
    import ui.page_storyboard as PS
    PS.sb_api.load_apercus = lambda sid: {"paths": [], "active_idx": 0}
    from PyQt6.QtWidgets import QWidget
    _par = QWidget()
    dlg = PS._MoodBatchDialog(_par, [{"id": "a", "number": 1, "scene_title": "T"}])
    for a in ("_opt_engine", "_opt_chars", "_opt_decor", "_opt_floor"):
        assert hasattr(dlg, a), "option manquante : " + a
    assert [dlg._opt_engine.itemData(i) for i in range(dlg._opt_engine.count())] == ["nb2", "flux"]
    assert dlg._opt_chars.isChecked() and dlg._opt_decor.isChecked() and dlg._opt_floor.isChecked()
    # Flux → références grisées (elles ne valent que pour NB2)
    _fi = next(k for k in range(dlg._opt_engine.count()) if dlg._opt_engine.itemData(k) == "flux")
    dlg._opt_engine.setCurrentIndex(_fi)
    assert not (dlg._opt_chars.isEnabled() or dlg._opt_decor.isEnabled() or dlg._opt_floor.isEnabled())
    # Le handler lit les options et les passe au worker
    cls = next(c for n, c in vars(PS).items()
               if isinstance(c, type) and hasattr(c, "_on_batch_mood"))
    obm = inspect.getsource(cls._on_batch_mood)
    assert "dlg._opt_engine.currentData()" in obm and "options=_mood_opts" in obm
    # run_mood : routage moteur + _shot_ref_images à toggles ; worker accepte options
    import api.apercu as A
    rm = inspect.getsource(A.run_mood)
    assert 'engine == "nb2"' in rm and "run_generation_nb2(" in rm and "run_generation(" in rm
    assert A._shot_ref_images({"character_ids": [], "decor_id": ""},
                              include_chars=False, include_decor=False) == []
    assert "options" in inspect.signature(A.MoodBatchWorker.__init__).parameters


@test
def rendu_audio_repliable_lipsync_ordre():
    """RENDU & AUDIO est un menu déroulant (replié par défaut). Bloc lip-sync :
    « Moteur lip-sync » AVANT la description, alignés."""
    import inspect
    from PyQt6.QtWidgets import QLabel
    import ui.tab_t2v as M
    tab = M.TabT2V()
    # Repliable
    assert hasattr(tab, "_raccords_toggle_btn") and hasattr(tab, "_raccords_body")
    assert tab._raccords_body.isHidden(), "RENDU & AUDIO doit être replié par défaut"
    tab._raccords_toggle_btn.click()
    assert not tab._raccords_body.isHidden(), "clic = déplier"
    tab._raccords_toggle_btn.click()
    assert tab._raccords_body.isHidden(), "re-clic = replier"
    # Lip-sync : la description n'est plus dans le toggle ; moteur + description dans le corps
    tlbls = [l.text() for l in tab._lipsync_toggle_row.findChildren(QLabel)]
    assert not any("Après génération" in t for t in tlbls), "description encore dans le toggle"
    blbls = [l.text() for l in tab._raccords_body.findChildren(QLabel)]
    assert any("Moteur lip-sync" in t for t in blbls) and any("Après génération" in t for t in blbls)
    # Moteur AVANT description (ordre dans le code)
    src = inspect.getsource(M.TabT2V)
    assert src.index("addWidget(_ls_row)") < src.index("addWidget(_ls_desc_wrap)"), \
        "« Moteur lip-sync » doit précéder la description"


@test
def sync_storyboard_casting_accessoires_vehicules():
    """Fenêtre Synchronisation du storyboard : 3 nouvelles options (casting, accessoires,
    véhicules) qui ré-assignent par nom les éléments cités dans le titre/prompt de chaque plan."""
    from ui.dialog_storyboard_sync import StoryboardSyncConfirmDialog
    keys = [o[0] for o in StoryboardSyncConfirmDialog._OPTIONS]
    for k in ("sync_casting", "sync_accessories", "sync_vehicles"):
        assert k in keys, "option absente : " + k
    # Réassignation effective (worker, sans IA)
    import api.screenplay as sp
    import core.casting as cast, core.decors as dec
    import core.accessories as acc, core.vehicles as veh
    _orig = (cast.list_characters, dec.list_decors, acc.list_accessories, veh.list_vehicles)
    try:
        cast.list_characters = lambda: [{"id": "c1", "name": "Raoul"}]
        dec.list_decors      = lambda: []
        acc.list_accessories = lambda: [{"id": "a1", "name": "Katana", "description": ""}]
        veh.list_vehicles    = lambda: [{"id": "v1", "name": "Mustang"}]
        shots = [{"id": "s1", "number": 1,
                  "scene_title": "Raoul dégaine son Katana près de la Mustang",
                  "seedance_prompt": "x", "character_ids": [], "character_names": [],
                  "accessory_ids": [], "accessory_names": [],
                  "vehicle_ids": [], "vehicle_names": []}]
        w = sp.SyncStoryboardWorker(shots, {
            "sync_casting": True, "sync_accessories": True, "sync_vehicles": True,
            "reassign": False, "resync_decors": False, "rewrite_prompts": False})
        out = {}
        w.finished.connect(lambda s: out.update(shots=s))
        w._run()
        s = out["shots"][0]
        assert "c1" in s["character_ids"] and "Raoul" in s["character_names"], s
        assert "a1" in s["accessory_ids"] and "Katana" in s["accessory_names"], s
        assert "v1" in s["vehicle_ids"] and "Mustang" in s["vehicle_names"], s
    finally:
        cast.list_characters, dec.list_decors, acc.list_accessories, veh.list_vehicles = _orig
    # i18n
    import core.i18n as i18n
    for lab in ("Synchroniser le casting", "Synchroniser les accessoires",
                "Synchroniser les véhicules"):
        assert lab in i18n._FR_TO_EN, lab


@test
def file_dialogs_non_natifs_anti_crash_com():
    """Crash Windows à l'import de fichiers (« Importer des fichiers audio », etc.) :
    les dialogues NATIFS passent par le shell COM → RPC_E_CANTCALLOUT_ININPUTSYNCCALL
    (0x8001010d) / RPC_E_DISCONNECTED (0x80010108) dans pandora_fault.log. main.py force
    les dialogues Qt NON-NATIFS (DontUseNativeDialog) au démarrage."""
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "main.py"), encoding="utf-8") as f:
        src_main = f.read()
    assert "def _force_qt_file_dialogs" in src_main, "patch dialogues non-natifs absent"
    assert "_force_qt_file_dialogs()   # dialogues Qt non-natifs" in src_main, \
        "patch non appelé au démarrage"
    # La logique non-native + remplacement des statics vit dans ui/file_dialogs.py.
    with open(os.path.join(root, "ui", "file_dialogs.py"), encoding="utf-8") as f:
        src_fd = f.read()
    assert "DontUseNativeDialog" in src_fd, "option non-native manquante"
    # Couvre ouverture (simple + multiple) ET sauvegarde
    for m in ("getOpenFileName", "getOpenFileNames", "getSaveFileName"):
        assert f"QFileDialog.{m}" in src_fd, "méthode non couverte : " + m


@test
def davinci_edit_lancement_sans_nameerror():
    """« Modifier depuis DaVinci » : le lancement de la file ne référence aucune variable
    inexistante (régression NameError « name 'checked' is not defined » au clic
    « Lancer la file d'attente » — la liste des clips s'appelle `selected`)."""
    import inspect
    src = inspect.getsource(__import__("ui.tab_davinci_edit", fromlist=["_"]))
    assert "len(checked)" not in src, "NameError : 'checked' non défini (utiliser `selected`)"


@test
def draw_to_video_vignette_remplace_popup():
    """Draw-to-Video (Modifier depuis DaVinci) : le dessin est confirmé par une VIGNETTE
    (croix pour la retirer) au lieu d'un pop-up ; le dessin reste un GUIDE (draw_guidance
    via Claude Vision), jamais une ref littérale envoyée au modèle."""
    import inspect, os, tempfile
    from PyQt6.QtGui import QPixmap
    import ui.tab_davinci_edit as M
    tab = M.TabDavinciEdit()
    assert hasattr(tab, "_draw_thumb_g") and hasattr(tab, "_draw_thumb_p")
    assert tab._draw_thumb_g.isHidden() and tab._draw_thumb_p.isHidden()
    # Plus de pop-up : le handler rafraîchit la vignette
    oh = inspect.getsource(M.TabDavinciEdit._on_draw_to_video)
    assert "_refresh_draw_thumb()" in oh, "vignette non rafraîchie après dessin"
    assert "Dessin enregistré pour" not in oh, "pop-up de validation encore présent"
    # Le clip dessiné devient ACTIF (sinon, mono-clip non sélectionné → vignette invisible)
    assert "self._active_clip_idx = idx" in oh, "clip dessiné non marqué actif (vignette KO)"
    # Dessiner → vignette ; croix → retirée
    d = tempfile.mkdtemp(); p = os.path.join(d, "a.png"); QPixmap(60, 60).save(p)
    tab._active_clip_idx = 0
    tab._draw_images[0] = p
    tab._refresh_draw_thumb()
    assert not tab._draw_thumb_g.isHidden() and not tab._draw_thumb_g_lbl.isHidden()
    tab._on_clear_draw()
    assert 0 not in tab._draw_images and tab._draw_thumb_g.isHidden()
    # Le dessin reste un GUIDE (jamais une ref littérale)
    pn = inspect.getsource(M.TabDavinciEdit._process_next)
    assert 'params["draw_guidance_path"]' in pn, "draw_guidance non transmis"
    # Aide explicative présente (i18n)
    import core.i18n as i18n
    assert any("Claude Vision" in k for k in i18n._FR_TO_EN), "texte d'aide Draw-to-Video absent"


@test
def plan_decor_variation_import_resync():
    """Plan des décors : l'aperçu du plan d'architecte propose « créer une variation
    (calée sur l'ensemble) » + « importer une image ». Le changement affecte le décor
    ET ses frères de pièce (room_group) → Mise en scène / Plan de feu lisent en direct."""
    import inspect, os, tempfile
    import ui.page_decors as PD
    import core.decors as dec
    # UI : aperçu avec les 2 options
    src = inspect.getsource(PD.PageDecors._open_plan_preview)
    assert "Créer une variation" in src and "Importer une image" in src
    assert "_on_plan_variation" in src and "_on_plan_import" in src
    # Worker de variation calé sur l'ensemble (overview en référence)
    from api.nano_banana import GenerateFloorPlanVariationWorker
    w = GenerateFloorPlanVariationWorker("a", "/ov.png", "salon")
    assert hasattr(w, "done") and w._ov == "/ov.png"
    # Propagation room_group + resync (set_floor_plan sur tous les frères)
    page = PD.PageDecors()
    calls, _orig = [], dec.set_floor_plan
    dec.set_floor_plan = lambda did, p: calls.append(did)
    try:
        d = tempfile.mkdtemp(); p = os.path.join(d, "fp.png"); open(p, "wb").write(b"x")
        page._all_items = [{"id": "a", "room_group": "Salon"},
                           {"id": "b", "room_group": "Salon"}, {"id": "c"}]
        page.refresh = lambda: None   # éviter le rechargement disque pendant le test
        page._apply_floor_plan_by_id("a", p)
        assert sorted(calls) == ["a", "b"], ("propagation room_group", calls)
        calls.clear()
        page._apply_floor_plan_by_id("c", p)   # décor libre → lui seul
        assert calls == ["c"], calls
    finally:
        dec.set_floor_plan = _orig
    import core.i18n as i18n
    assert "Créer une variation (calée sur l'ensemble)" in i18n._FR_TO_EN


@test
def film_reel_auto_coche_en_style_realiste():
    """RENDU & AUDIO : en style « Film réaliste » (key 'realistic'), le toggle
    « Prise de vue réelle » se coche automatiquement. On ne décoche jamais hors
    de ce style (choix de l'utilisateur préservé). showEvent déclenche la synchro."""
    import inspect
    import core.style as style
    from PyQt6.QtWidgets import QApplication, QCheckBox
    QApplication.instance() or QApplication([])
    import ui.tab_t2v as T

    class _Stub:
        pass
    s = _Stub()
    s._film_anchor_cb = QCheckBox()
    _orig = style.get_style_key
    try:
        style.get_style_key = lambda: "realistic"
        T.TabT2V._sync_film_anchor_with_style(s)
        assert s._film_anchor_cb.isChecked(), "non coché en style réaliste"
        # Hors style réaliste : on ne décoche PAS ce qui est coché.
        style.get_style_key = lambda: "noir"
        T.TabT2V._sync_film_anchor_with_style(s)
        assert s._film_anchor_cb.isChecked(), "ne doit pas décocher hors réaliste"
        # Décoché + style non réaliste → reste décoché.
        s._film_anchor_cb.setChecked(False)
        T.TabT2V._sync_film_anchor_with_style(s)
        assert not s._film_anchor_cb.isChecked(), "ne doit pas cocher hors réaliste"
    finally:
        style.get_style_key = _orig
    assert "_sync_film_anchor_with_style" in inspect.getsource(T.TabT2V.showEvent)


@test
def sound_design_moteurs_multiples():
    """Sound Design : sélecteur de moteur sur le panneau TEXTE (ElevenLabs SFX V2 par
    défaut · MMAudio V2 · Mirelo) + MMAudio ajouté au panneau VIDÉO (réf vidéo).
    _make_text_worker route le bon worker (partagé manuel + file par plan)."""
    import inspect, tempfile
    import api.tts as tts
    # Workers + endpoints fal vérifiés
    assert "fal-ai/elevenlabs/sound-effects/v2" in inspect.getsource(tts.ElevenLabsSFXWorker._real)
    assert "fal-ai/mmaudio-v2/text-to-audio" in inspect.getsource(tts.MMAudioTextWorker._real)
    assert "fal-ai/mmaudio-v2" in inspect.getsource(tts.MMAudioVideoWorker._real)
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import ui.tab_sound_design as SD
    tab = SD.TabSoundDesign()
    tkeys = [tab._text_engine_combo.itemData(i) for i in range(tab._text_engine_combo.count())]
    assert tkeys[0] == "elevenlabs", ("ElevenLabs doit être le défaut", tkeys)
    assert set(tkeys) >= {"elevenlabs", "mmaudio", "sfx16"}, tkeys
    vkeys = [tab._video_engine_combo.itemData(i) for i in range(tab._video_engine_combo.count())]
    assert set(vkeys) >= {"sfx16", "foley", "mmaudio"}, vkeys
    tab._sfx_out_dir = lambda: tempfile.mkdtemp()
    tab._text_engine_combo.setCurrentIndex(tkeys.index("mmaudio"))
    assert isinstance(tab._make_text_worker("x", 5.0, "t"), tts.MMAudioTextWorker)
    tab._text_engine_combo.setCurrentIndex(tkeys.index("elevenlabs"))
    assert isinstance(tab._make_text_worker("x", 5.0, "t"), tts.ElevenLabsSFXWorker)


@test
def file_dialog_vignettes_images():
    """Dialogues de fichiers : vignettes d'images dans l'explorateur (QFileIconProvider)
    + non-natif (anti-crash COM) + iconSize agrandi. Les statics QFileDialog sont
    remplacées par des versions instance (format de retour conservé)."""
    import os, inspect, tempfile
    from PyQt6.QtWidgets import QApplication, QFileDialog, QListView
    from PyQt6.QtCore import QFileInfo
    from PyQt6.QtGui import QPixmap
    QApplication.instance() or QApplication([])
    import ui.file_dialogs as FD
    # 1) vignette générée pour une image + mise en cache
    d = tempfile.mkdtemp()
    img = os.path.join(d, "x.png")
    QPixmap(80, 80).save(img)
    prov = FD.ThumbnailIconProvider()
    ic = prov.icon(QFileInfo(img))
    assert not ic.isNull(), "vignette image absente"
    assert QFileInfo(img).absoluteFilePath() in prov._cache, "vignette non mise en cache"
    # 2) apply_thumbnails : non-natif + provider + iconSize agrandi
    dlg = QFileDialog()
    FD.apply_thumbnails(dlg)
    assert dlg.testOption(QFileDialog.Option.DontUseNativeDialog), "dialogue natif (risque COM)"
    assert dlg.iconProvider() is FD._shared_provider(), "icon provider non posé"
    sizes = [lv.iconSize().width() for lv in dlg.findChildren(QListView)]
    assert sizes and max(sizes) >= 48, ("iconSize non agrandi", sizes)
    # P4 — boutons Ouvrir/Annuler stylés pour la lisibilité sur fond sombre (retour Pierre)
    from PyQt6.QtWidgets import QDialogButtonBox
    assert hasattr(FD, "_style_dialog_buttons"), "helper de style des boutons absent"
    _accept_styled = any(
        bb.buttonRole(b) == QDialogButtonBox.ButtonRole.AcceptRole and b.styleSheet()
        for bb in dlg.findChildren(QDialogButtonBox) for b in bb.buttons()
    )
    assert _accept_styled, "bouton Ouvrir non stylé (P4 lisibilité)"
    dlg.deleteLater()
    # 3) install remplace bien les 3 statics (sans les exécuter — source)
    src = inspect.getsource(FD.install_thumbnail_file_dialogs)
    for m in ("getOpenFileName", "getOpenFileNames", "getSaveFileName"):
        assert f"QFileDialog.{m}" in src, f"static {m} non remplacée"


@test
def edit_clip_duree_calee_sur_source():
    """« Modifier un clip » : la durée de régénération est calée sur le clip SOURCE
    (ffprobe, bornée 4–15 s) au lieu d'un 5 s figé. En lip-sync, l'audio est aligné
    sur cette durée (conform_audio_duration + target_duration au worker)."""
    import inspect
    import core.video_utils as vu
    import ui.tab_davinci_edit as M

    class _Stub:
        pass
    s = _Stub()
    s._clips_data = [{"file_path": "x.mp4"}]
    _orig = vu.video_duration_s
    try:
        vu.video_duration_s = lambda p: 8.4
        assert M.TabDavinciEdit._source_gen_duration(s, 0) == 8, "arrondi"
        vu.video_duration_s = lambda p: 2.0
        assert M.TabDavinciEdit._source_gen_duration(s, 0) == 4, "borne min 4 s"
        vu.video_duration_s = lambda p: 40.0
        assert M.TabDavinciEdit._source_gen_duration(s, 0) == 15, "borne max 15 s"
        vu.video_duration_s = lambda p: 0.0
        assert M.TabDavinciEdit._source_gen_duration(s, 0) == 5, "repli 5 s"
    finally:
        vu.video_duration_s = _orig
    # Plus de durée figée : _process_next utilise la durée calée + la mémorise.
    src_pn = inspect.getsource(M.TabDavinciEdit._process_next)
    assert "_source_gen_duration(clip_idx)" in src_pn, "durée non calée sur la source"
    assert '"duration":     gen_dur' in src_pn, "params['duration'] encore figé"
    # Lip-sync : worker accepte target_duration + cale l'audio.
    import api.lipsync as LS
    assert hasattr(LS, "conform_audio_duration"), "helper d'alignement audio absent"
    assert "target_duration" in inspect.signature(LS.LipSyncWorker.__init__).parameters
    assert "conform_audio_duration" in inspect.getsource(LS.LipSyncWorker._run)
    assert "target_duration" in inspect.getsource(M.TabDavinciEdit._start_lipsync)


@test
def edit_clip_rendu_audio_et_modeles():
    """Modifier un clip : section repliable RENDU & AUDIO contenant le lip-sync, et
    menu déroulant « Type de modification » qui insère un modèle de prompt (décor /
    visage / étalonnage / tenue) dans le prompt global."""
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import ui.tab_davinci_edit as M
    tab = M.TabDavinciEdit()
    # 1) RENDU & AUDIO repliable + lip-sync à l'intérieur
    assert hasattr(tab, "_ra_container") and hasattr(tab, "_ra_body"), "section RENDU & AUDIO absente"
    assert tab._cb_lipsync is not None, "lip-sync absent"
    assert tab._ra_body.isAncestorOf(tab._lipsync_toggle_row), "lip-sync hors de RENDU & AUDIO"
    assert not tab._ra_body.isVisible(), "RENDU & AUDIO doit être replié par défaut"
    # 1b) mêmes options que le storyboard (les 5 applicables), DANS la section + câblées
    for _attr, _row in (("_audio_cb", "_audio_toggle_row"), ("_music_cb", "_music_toggle_row"),
                        ("_subtitle_cb", "_subtitle_toggle_row"),
                        ("_film_anchor_cb", "_film_anchor_toggle_row"),
                        ("_dyn_cam_cb", "_dyn_cam_toggle_row")):
        assert getattr(tab, _attr, None) is not None, f"{_attr} absent"
        assert tab._ra_body.isAncestorOf(getattr(tab, _row)), f"{_row} hors de RENDU & AUDIO"
    assert tab._audio_cb.isChecked(), "Audio natif coché par défaut (comme storyboard)"
    import inspect as _insp
    src_pn = _insp.getsource(M.TabDavinciEdit._process_next)
    assert '"audio":' in src_pn and "no_music_suffix" in src_pn, "audio/musique non câblés"
    assert "no subtitles" in src_pn and "ARRI Alexa 35mm" in src_pn, "sous-titres/film non câblés"
    assert "change the camera angle every 2 seconds" in src_pn, "caméra dynamique non câblée"
    # 2) menu déroulant des 4 modèles + invite
    keys = [tab._mod_combo.itemData(i) for i in range(tab._mod_combo.count())]
    assert keys[0] == "" and set(keys) >= {"bg", "face", "grade", "outfit"}, keys
    # 3) insertion d'un modèle Seedance dans le prompt global + reset du sélecteur
    #    (« étalonnage » : modèle Seedance ponctuel ; « face » est traité à part = autre moteur)
    tab._prompt_global.setPlainText("")
    tab._on_mod_template(keys.index("grade"))
    txt = tab._prompt_global.toPlainText().lower()
    assert "@video1" in txt and "étalonnage" in txt, txt[:80]
    assert tab._mod_combo.currentIndex() == 0, "le sélecteur doit revenir sur l'invite (modèle Seedance)"
    # non destructif : 2e insertion à la suite (tenue = modèle Seedance ponctuel)
    tab._on_mod_template(keys.index("outfit"))
    full = tab._prompt_global.toPlainText().lower()
    assert "étalonnage" in full and "tenue" in full, "insertion non cumulative"


@test
def edit_clip_pixverse_engine():
    """Pixverse Swap = MOTEUR de génération sélectionnable (visage / fond), étiqueté ;
    Seedance 2.0 reste le DÉFAUT. Le menu « Type de modification » réinsère le prompt
    Seedance auto (visage inclus). Routage dans _process_next par _pixverse_engine_mode()."""
    import inspect
    import api.face_swap as FS
    assert "fal-ai/pixverse/swap" in inspect.getsource(FS.PixverseSwapWorker.run), "endpoint Pixverse absent"
    w = FS.PixverseSwapWorker("v.mp4", "f.png", mode="person", resolution="1080p")
    assert w._mode == "person" and w._res == "720p", "1080p doit être clampé à 720p"
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import ui.tab_davinci_edit as M
    tab = M.TabDavinciEdit()
    # Défaut = Seedance (pas de swap Pixverse)
    assert tab._pixverse_engine_mode() == "", ("défaut ≠ Pixverse", tab._get_model())
    # Les 2 moteurs Pixverse sont dans le SÉLECTEUR DE MOTEUR, étiquetés visage/fond
    ekeys = [tab._cb_model.itemData(i) for i in range(tab._cb_model.count())]
    assert "pixverse_face" in ekeys and "pixverse_bg" in ekeys, ekeys
    tab._cb_model.setCurrentIndex(ekeys.index("pixverse_face"))
    assert tab._pixverse_engine_mode() == "person", "moteur visage non détecté"
    assert not tab._modif_hint.isHidden(), "indice moteur Pixverse non affiché"
    tab._cb_model.setCurrentIndex(ekeys.index("pixverse_bg"))
    assert tab._pixverse_engine_mode() == "background", "moteur fond non détecté"
    # « Type de modification » → « Changer un visage » RÉINSÈRE le prompt Seedance auto
    mkeys = [tab._mod_combo.itemData(i) for i in range(tab._mod_combo.count())]
    tab._prompt_global.setPlainText("")
    tab._on_mod_template(mkeys.index("face"))
    txt = tab._prompt_global.toPlainText().lower()
    assert "@video1" in txt and "@image1" in txt and "visage" in txt, txt[:80]
    assert tab._mod_combo.currentIndex() == 0, "le sélecteur revient sur l'invite"
    # routage par MOTEUR dans _process_next
    src = inspect.getsource(M.TabDavinciEdit._process_next)
    assert "_pixverse_engine_mode()" in src and "PixverseSwapWorker" in src, "routage Pixverse (moteur) absent"


@test
def sound_design_tirette_duree_et_traduction():
    """Sound Design : (1) le prompt est TRADUIT en anglais avant l'envoi (workers SFX) ;
    (2) la durée est une TIRETTE dont le max s'adapte au moteur (ElevenLabs 22 s, autres 30 s)."""
    import inspect
    import api.tts as tts
    for cls in (tts.ElevenLabsSFXWorker, tts.SFX1Worker, tts.MMAudioTextWorker):
        assert "_sfx_prompt_en(self._text)" in inspect.getsource(cls._real), (cls.__name__, "non traduit")
    from PyQt6.QtWidgets import QApplication, QSlider
    QApplication.instance() or QApplication([])
    import ui.tab_sound_design as SD
    tab = SD.TabSoundDesign()
    assert isinstance(tab._dur_text, QSlider) and isinstance(tab._dur_video, QSlider), "la durée doit être une tirette"
    tk = [tab._text_engine_combo.itemData(i) for i in range(tab._text_engine_combo.count())]
    tab._text_engine_combo.setCurrentIndex(tk.index("elevenlabs"))
    assert tab._dur_text.maximum() == 22, ("ElevenLabs = 22 s", tab._dur_text.maximum())
    tab._dur_text.setValue(22)
    tab._text_engine_combo.setCurrentIndex(tk.index("mmaudio"))
    assert tab._dur_text.maximum() == 30, ("MMAudio = 30 s", tab._dur_text.maximum())
    # clamp : repasser sur ElevenLabs (22) ramène une valeur de 30 → 22
    tab._dur_text.setValue(30)
    tab._text_engine_combo.setCurrentIndex(tk.index("elevenlabs"))
    assert tab._dur_text.value() <= 22, ("durée ramenée au max moteur", tab._dur_text.value())


@test
def analyse_arrangement_sauvegardee():
    """« Analyse & co-écriture » (ex-Proposer un arrangement) : l'analyse est
    PERSISTÉE avec le scénario et ROUVERTE sans nouvel appel API (crédits
    préservés) ; « Relancer l'analyse » vit dans la fenêtre."""
    import inspect
    import core.storyboard as sb
    sb.set_namespace("storyboard")
    import ui.page_scenario as _m
    src = inspect.getsource(_m)
    assert "Analyse & co-écriture" in src, "bouton renommé"
    assert "_start_arrange_analysis" in src, "relance = méthode dédiée"
    assert "arrange_analysis" in src, "analyse persistée avec le scénario"
    assert "Relancer l'analyse" in src, "bouton Relancer dans la fenêtre"
    from ui.page_scenario import PageScenario
    p = PageScenario()
    p._set_editor_text("INT. CUISINE - NUIT\nUne scène de test.")
    p._current = {"arrange_analysis": "ANALYSE PERSISTÉE"}
    calls = []
    p._open_arrange_window = lambda analysis="", worker=None: calls.append((analysis, worker))
    p._on_arrange()
    assert calls == [("ANALYSE PERSISTÉE", None)], \
        "réouverture SANS worker (aucun crédit consommé)"
    assert p._last_analysis == "ANALYSE PERSISTÉE"
    # Erreur « crédits épuisés » → message clair (API texte ; fal.ai a le sien
    # dans core.worker.humanize_api_error)
    from core.ai_provider import humanize_ai_error
    assert "console.anthropic.com" in humanize_ai_error("Your credit balance is too low")
    assert "réessaie" in humanize_ai_error("Error 429: rate limit exceeded")
    assert humanize_ai_error("autre erreur") == "autre erreur"


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


@test
def seed_reprise_et_4k():
    """4K best-effort dans Seedance 2.0 (essai, défaut 1080p conservé) + reprise
    d'un plan validé par sa GRAINE depuis l'Historique (prompt + graine verrouillée
    → onglet « Générer depuis Storyboard »). Fige les 2 chantiers 2026-07-04."""
    import ui.tab_t2v as t2v
    vals = [v for _, v in t2v._ENGINE_RESOLUTIONS["seedance-2.0"]]
    assert vals[0] == "4k", "le 4K (validé) doit être EN TÊTE de la liste Seedance 2.0"
    assert t2v._ENGINE_DEFAULT_RES.get("seedance-2.0") == "720p", "défaut Seedance = 720p"
    entry = {"prompt": "plan nuit neons", "seed": 424242, "status": "done"}
    w = t2v.TabT2V()
    assert w.cb_res.currentData() == "720p", \
        f"le combo résolution doit présélectionner 720p, pas {w.cb_res.currentData()}"
    w.prefill_from_seed(dict(entry))
    assert "plan nuit neons" in w.prompt_ta.toPlainText(), "prompt non réinjecté"
    assert w._last_seed == 424242 and w._get_seed() == 424242, "graine non verrouillée"
    # Historique : signal + bouton « ↑ HD » conditionnel (done + seed>0 seulement)
    import ui.tab_history as th
    from PyQt6.QtWidgets import QPushButton
    assert hasattr(th.TabHistory, "reprendre_plan"), "signal reprendre_plan manquant"
    hist = th.TabHistory()
    assert hist._make_item(dict(entry)).findChildren(QPushButton), "bouton HD absent (done+seed)"
    assert not hist._make_item({**entry, "seed": 0}).findChildren(QPushButton), "bouton sans graine"
    assert not hist._make_item({**entry, "status": "error"}).findChildren(QPushButton), "bouton sur erreur"
    # Câblage bout-en-bout : reprise → pré-remplit T2V + bascule
    from ui.seedance_widget import SeedanceWidget
    sw = SeedanceWidget()
    sw.tab_history.reprendre_plan.emit(dict(entry))
    assert sw.tabs.currentWidget() is sw.tab_t2v, "bascule onglet T2V manquante"
    assert "plan nuit neons" in sw.tab_t2v.prompt_ta.toPlainText(), "prompt non transmis au widget"
    # Vidéothèque « ↑ HD » : MÊME reprise par la graine que l'Historique (2026-07-07).
    from ui.tab_video_library import _VideoCard, TabVideoLibrary
    import core.history as _H
    assert hasattr(_VideoCard, "reprise_requested") and hasattr(TabVideoLibrary, "send_to_reprise")
    assert callable(getattr(_H, "find_entry_by_path", None)), "find_entry_by_path absent"
    sw.tab_t2v.prompt_ta.setPlainText("")
    sw.tabs.setCurrentWidget(sw.tab_library)
    sw.tab_library.send_to_reprise.emit({"prompt": "reprise videotheque cine", "seed": 555, "status": "done"})
    assert sw.tabs.currentWidget() is sw.tab_t2v, "Vidéothèque HD → bascule T2V (comme Historique)"
    assert "reprise videotheque cine" in sw.tab_t2v.prompt_ta.toPlainText(), "Vidéothèque HD : prompt non transmis"


@test
def references_inspiration_par_plan():
    """Colonne « Référence » (2026-07-05) : images d'inspiration par plan → injectées
    en Seedance avec le rôle « reference » (« s'inspirer de », PAS un rendu identique).
    Modèle partagé Cinéma/Live (core.storyboard) ; limite refs montée 4→9 ; dialogue
    max 3 images (fichier + bibliothèque)."""
    import core.storyboard as sb
    s = sb.save_shot({"scene_title": "escalier infini", "number": 1})
    assert "reference_images" in s and isinstance(s["reference_images"], list), "champ modèle absent"
    rsrc = inspect.getsource(__import__("api.real", fromlist=["x"]))
    assert 'elif _role == "reference":' in rsrc and "INSPIRATION REFERENCE" in rsrc, "rôle reference manquant"
    assert "Loosely draw inspiration" in rsrc and "Do NOT copy it literally" in rsrc, "ton inspiration"
    assert "ref_images[:9]" in rsrc, "limite refs non montée à 9"
    # Injection dans la génération, Cinéma ET Live
    for mod in ("ui.tab_t2v", "ui.tab_t2v_live"):
        msrc = inspect.getsource(__import__(mod, fromlist=["x"]))
        assert 'ref_image_roles + ["reference"]' in msrc, f"{mod} : reference_images non injectées"
    from ui.dialog_reference_images import ReferenceImagesDialog, MAX_REFS
    assert MAX_REFS == 3, "dialogue max 3 images"


@test
def moteurs_image_multi():
    """Moteurs d'image : GPT Image 2 / FLUX.2 pro / Seedream 4.5 / Recraft ajoutés au
    registre + câblés (params image_size) ; combos casting/décor peuplés depuis le
    registre (Matthieu 2026-07-13)."""
    from core.config import IMAGE_MODEL_ENDPOINTS, IMAGE_MODEL_LABELS, IMAGE_SIZE_MODELS
    from api.nano_banana import _build_image_args
    for k in ("gpt2", "flux2", "seedream45", "recraft"):
        assert k in IMAGE_MODEL_ENDPOINTS and k in IMAGE_MODEL_LABELS, f"{k} au registre"
        assert k in IMAGE_SIZE_MODELS, f"{k} utilise image_size"
    assert IMAGE_MODEL_ENDPOINTS["gpt2"] == "openai/gpt-image-2"
    assert IMAGE_MODEL_ENDPOINTS["flux2"] == "fal-ai/flux-2-pro"
    # Args par modèle : Nano Banana garde aspect_ratio ; les nouveaux passent en image_size.
    _, a_nb = _build_image_args("p", "2:3", "1K", {"image_model": "nb2"}, 1)
    assert "aspect_ratio" in a_nb and "image_size" not in a_nb, "NB : aspect_ratio conservé"
    _, a_gpt = _build_image_args("p", "16:9", "1K", {"image_model": "gpt2"}, 1)
    assert a_gpt.get("image_size") == "landscape_16_9" and "aspect_ratio" not in a_gpt, \
        "GPT Image 2 : aspect_ratio → image_size"
    _, a_rc = _build_image_args("p", "1:1", "1K", {"image_model": "recraft"}, 1)
    assert set(a_rc) == {"prompt", "image_size"}, "recraft : params minimaux (pas d'unknown field)"
    # Combos peuplés depuis le registre → les 6 modèles apparaissent.
    from ui.dialog_character import CharacterDialog
    dlg = CharacterDialog(None)
    keys = {dlg._model_combo.itemData(i) for i in range(dlg._model_combo.count())}
    assert {"nb2", "nb_pro", "gpt2", "flux2", "seedream45", "recraft"} <= keys, \
        "combo casting peuplé depuis le registre (6 modèles)"


@test
def sheet_casting_visage_gros_plan_seulement():
    """Sheet casting : SEUL le gros plan (bust) porte le visage ; les vues de corps
    (face/3-4/profil/dos) sont recadrées SANS visage (tête hors champ) → Seedance ne
    reçoit qu'UN visage de référence (Matthieu 2026-07-13, évite la confusion)."""
    from api.nano_banana import _VIEW_DEFS, _SHEET_SUFFIX
    by = {k: (instr, pulid) for k, instr, pulid in _VIEW_DEFS}
    for k in ("front", "34", "profile"):
        instr, pulid = by[k]
        assert "CROPPED OUT" in instr and "NO head" in instr, f"{k} : tête hors champ"
        assert pulid is False, f"{k} : injection d'identité coupée (aucun visage)"
    assert by["bust"][1] is True, "le gros plan (bust) porte le visage"
    assert ("head CROPPED OUT" in _SHEET_SUFFIX
            and "ONLY view showing the face" in _SHEET_SUFFIX), \
        "sheet 1-image : visage uniquement sur le gros plan"


@test
def coecriture_scenario_chirurgicale():
    """Co-écriture Cinéma : le chat de scénario est CHIRURGICAL (répond aux questions
    OU applique des éditions ciblées find/replace — jamais de réécriture totale), et
    un bouton « Générer le scénario » fait la réécriture complète volontaire.
    Demande Matthieu 2026-07-13 (ne pas dépenser tous les tokens sur du Q&R)."""
    import inspect
    from api.screenplay import ArrangeChatWorker, _parse_surgical_reply
    from core.text_edits import apply_find_replace_edits
    # Worker : mode chirurgical disponible + signal edits_ready.
    assert "surgical" in inspect.signature(ArrangeChatWorker.__init__).parameters, \
        "ArrangeChatWorker accepte surgical="
    assert hasattr(ArrangeChatWorker, "edits_ready"), "signal edits_ready(list)"
    # Parsing : question → 0 édit (aucune réécriture) ; demande → find/replace.
    m, e = _parse_surgical_reply('{"message":"réponse à la question","edits":[]}')
    assert m == "réponse à la question" and e == [], "Q&R pure → aucune édition"
    m, e = _parse_surgical_reply(
        '{"message":"ok","edits":[{"find":"AAA","replace":"BBB","summary":"s"}]}')
    assert len(e) == 1 and e[0]["find"] == "AAA", "édition ciblée extraite"
    new, applied, missed = apply_find_replace_edits("xx AAA yy", e)
    assert new == "xx BBB yy" and len(applied) == 1 and not missed, "find/replace chirurgical"
    # ── Fixes 2026-07-13 (retour Matthieu : « parfois ça n'écrit plus les modifs ») ──
    # (a) TYPOGRAPHIE : le texte utilise ' « » – … mais le modèle renvoie ' " - ...
    #     → le repli doit matcher malgré les variantes typographiques.
    _txt = "Il l’observe… puis sort — « Adieu »."
    _ed  = [{"find": "Il l'observe... puis sort - \"Adieu\".", "replace": "OK", "summary": ""}]
    _new, _ap, _mi = apply_find_replace_edits(_txt, _ed)
    assert _new == "OK" and _ap and not _mi, \
        f"variantes typographiques non tolérées (obtenu : {_new!r})"
    # (b) ANTI-TRONCATURE : 4096 coupait le JSON (plusieurs passages longs → 0 édition).
    _wsrc = inspect.getsource(ArrangeChatWorker.run)
    assert "_maxtok = 8192" in _wsrc, "chirurgical : plafond 8192 requis"
    # (c) PROMPT : jamais « je vais modifier » sans édition ; réponses AÉRÉES (paragraphes).
    from api.screenplay import _arrange_chat_surgical_system
    _p = _arrange_chat_surgical_system(5)
    assert "IMPÉRATIF" in _p and "AÉRÉE" in _p, \
        "prompt chirurgical : règle anti-promesse + réponses aérées"
    # Dialog : chat chirurgical par défaut + bouton de réécriture complète.
    from ui.dialog_arrange_session import ArrangeSessionDialog
    dlg = ArrangeSessionDialog(None, "INT. MAISON — JOUR\nLIA\nBonjour.", "analyse", 5)
    assert hasattr(dlg, "_btn_generate"), "bouton « Générer le scénario » présent"
    assert hasattr(dlg, "_on_edits_ready"), "handler d'application chirurgicale"
    assert "surgical: bool = True" in inspect.getsource(dlg._start_worker), \
        "chat chirurgical par défaut"
    assert "surgical=False" in inspect.getsource(dlg._on_generate_full), \
        "le bouton « Générer » fait la réécriture complète"
    # Bulles : interligne aéré (les \n du message deviennent des <br> lisibles).
    import ui.dialog_arrange_session as _das
    _bh = inspect.getsource(_das._bubble_html)
    assert "line-height" in _bh and "<br>" in _bh, \
        "bulle de chat : sauts de ligne + interligne"


@test
def reference_image_visible_au_1er_ajout():
    """Ajouter une image de référence l'affiche DÈS le 1er ajout (bug « il fallait le
    faire 2 fois », 2026-07-09) : le handler sauve PUIS émet changed → la ligne se
    reconstruit depuis les données persistées, l'affichage n'est plus tributaire d'un
    widget local invalidé entre-temps."""
    import inspect
    from ui.page_storyboard import _ShotRow
    src = inspect.getsource(_ShotRow.__init__)
    i = src.find("def _open_refs")
    assert i != -1, "_open_refs (colonne Référence) introuvable"
    j = src.find("_clickable(ref_lbl", i)
    block = src[i:j if j != -1 else i + 1400]
    assert "save_shot" in block and "changed.emit" in block, \
        "l'ajout de référence doit émettre changed (refresh fiable dès le 1er ajout)"
    # Aperçu (2026-07-09) : les N images côte à côte et ENTIÈRES (fit inside), pas la 1re
    # seule recadrée. Le rendu passe par build_reference_thumb (helper partagé).
    from ui.dialog_reference_images import build_reference_thumb
    _bsrc = inspect.getsource(build_reference_thumb)
    assert "KeepAspectRatio" in _bsrc and "KeepAspectRatioByExpanding" not in _bsrc, \
        "vignette réf : images recadrées (doivent être fit-inside, non tronquées)"
    _rr_i = src.find("def _render_ref")
    _rr_j = src.find("_render_ref()", _rr_i)
    _rr = src[_rr_i:_rr_j if _rr_j != -1 else _rr_i + 900]
    assert "build_reference_thumb" in _rr and "KeepAspectRatioByExpanding" not in _rr, \
        "_render_ref Cinéma n'utilise pas la vignette composite non recadrée"
    assert build_reference_thumb([], 100, 58).isNull(), "aucune image → pas de vignette"


@test
def distributeur_video_piapi():
    """Distributeurs de génération vidéo (2026-07-16) : fal.ai = socle + repli,
    PiAPI = alternatif low cost choisi dans Paramètres → avancés. Les PRIX
    (pricing.estimate/format_estimate) suivent la grille du distributeur actif,
    et le Studio affiche l'estimation dans un bandeau FIXE sous les onglets."""
    import inspect
    import core.media_provider as mp
    from core import pricing

    # Registre : fal + piapi, fal par défaut sans config
    assert set(mp.PROVIDERS) >= {"fal", "piapi"}
    _orig_lc = mp.load_config
    try:
        mp.load_config = lambda: {}
        assert mp.get_video_provider() == "fal", "défaut = fal"
        assert mp.active_video_provider("seedance-2.0") == "fal"
        # PiAPI choisi SANS clé → repli fal (jamais d'appel sans clé)
        mp.load_config = lambda: {"video_provider": "piapi"}
        assert mp.active_video_provider("seedance-2.0") == "fal", "sans clé → fal"
        # PiAPI choisi AVEC clé → actif pour Seedance, repli fal pour un moteur non couvert
        mp.load_config = lambda: {"video_provider": "piapi", "piapi_key": "k"}
        assert mp.active_video_provider("seedance-2.0") == "piapi"
        assert mp.active_video_provider("seedance-2.0-fast") == "piapi"
        assert mp.active_video_provider("kling-v3-pro") == "fal", "non couvert → fal"
        # Prix : grille PiAPI (0.20 $/s en 720p) vs fal (0.30 $/s)
        cost, mode = pricing.estimate("seedance-2.0", "720p", 10.0, 1)
        assert mode == "s" and abs(cost - 2.0) < 1e-6, ("prix PiAPI attendu 2.0", cost)
        msg = pricing.format_estimate("Seedance 2.0", "seedance-2.0", "720p", 10.0, 2)
        assert "piapi.ai" in msg, "le rappel doit citer le distributeur actif"
        # Retour à fal → grille fal restaurée
        mp.load_config = lambda: {}
        cost_fal, _ = pricing.estimate("seedance-2.0", "720p", 10.0, 1)
        assert abs(cost_fal - 3.0) < 1e-6, ("prix fal attendu 3.0", cost_fal)
        assert "fal.ai" in pricing.format_estimate("S", "seedance-2.0", "720p", 10, 1)
    finally:
        mp.load_config = _orig_lc

    # Backend PiAPI : mapping des modes + durée clampée, AUCUN appel réseau ici
    from api import piapi
    inp = piapi.build_input("t2v", {"prompt": "p", "resolution": "720p",
                                    "duration": 99, "generate_audio": True})
    assert inp["mode"] == "text_to_video" and inp["duration"] == 15
    inp = piapi.build_input("i2v", {"image_url": "u1", "end_image_url": "u2",
                                    "duration": 8})
    assert inp["mode"] == "first_last_frames" and inp["image_urls"] == ["u1", "u2"]
    inp = piapi.build_input("ref", {"image_urls": ["a"], "video_urls": ["v"],
                                    "duration": 8})
    assert inp["mode"] == "omni_reference" and inp["image_urls"] == ["a"]
    # Routage dans run_real : préparation commune, bascule sur l'appel final
    import api.real as real
    _src = inspect.getsource(real.run_real)
    assert "active_video_provider" in _src and "run_piapi" in _src
    # Paramètres : combo distributeur + clé PiAPI persistés (auto-save)
    import ui.page_settings as PS
    _ssrc = inspect.getsource(PS.SettingsPage) if hasattr(PS, "SettingsPage") else \
        inspect.getsource(PS)
    assert "video_provider_combo" in _ssrc and '"piapi_key"' in _ssrc
    assert "test_piapi_connection" in _ssrc
    # Studio : bandeau prix fixe sous les onglets, branché sur le signal T2V
    import ui.seedance_widget as SW
    _wsrc = inspect.getsource(SW.SeedanceWidget)
    assert "_price_footer" in _wsrc and "price_estimate_changed" in _wsrc
    import ui.tab_t2v as T
    assert "price_estimate_changed" in inspect.getsource(T.TabT2V._refresh_price_estimate)

    # ── Mode MONO-distributeur : pas de repli + services grisés ──────────────
    _orig_lc2 = mp.load_config
    try:
        # Multi (défaut) : tout disponible, jamais bloqué
        mp.load_config = lambda: {}
        assert mp.get_distribution_mode() == "multi"
        assert mp.service_available("sound") == (True, "")
        assert mp.mono_blocked_engine("kling-v3-pro") == ""
        # Mono + PiAPI : Sound/Musique/Image/Upscale indisponibles avec message,
        # Seedance disponible ; moteur non couvert → BLOQUÉ (pas de repli fal)
        mp.load_config = lambda: {"video_provider": "piapi", "piapi_key": "k",
                                  "distribution_mode": "mono"}
        ok, msg = mp.service_available("sound")
        assert not ok and "fal.ai" in msg and "Multi-distributeurs" in msg
        assert mp.service_available("video_seedance") == (True, "")
        assert "indisponible" in mp.mono_blocked_engine("kling-v3-pro").lower()
        assert mp.mono_blocked_engine("seedance-2.0") == ""
        assert mp.active_video_provider("seedance-2.0") == "piapi"
        # Mono + PiAPI SANS clé : Seedance bloqué avec message « clé manquante »
        mp.load_config = lambda: {"video_provider": "piapi",
                                  "distribution_mode": "mono"}
        assert "manquante" in mp.mono_blocked_engine("seedance-2.0")
    finally:
        mp.load_config = _orig_lc2
    # run_real bloque AVANT l'appel ; le Studio grise les onglets (tooltip)
    assert "mono_blocked_engine" in _src
    assert "_apply_distribution_mode" in _wsrc and "setTabEnabled" in _wsrc
    # Paramètres : combo mode persisté
    assert "distribution_mode_combo" in _ssrc and '"distribution_mode"' in _ssrc


@test
def accessoire_import_photo_detourage():
    """Éléments (demande utilisateur 2026-07-16) : importer une PHOTO plutôt que
    générer (parité personnages) dans les 4 dialogs Accessoire/HMC/Véhicule/
    Décor, avec proposition de SUPPRIMER LE FOND (BiRefNet) à l'import —
    SAUF pour le Décor (un lieu se garde avec son fond). L'image importée/
    détourée rejoint la galerie et devient l'image active."""
    import inspect, tempfile
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QPixmap
    QApplication.instance() or QApplication([])
    import ui.dialog_accessory as DA
    import ui.dialog_hmc as DH
    import ui.dialog_vehicle as DV
    import ui.dialog_decor as DD
    # Avec détourage proposé : Accessoire, HMC, Véhicule
    for _cls in (DA.AccessoryDialog, DH.HMCDialog, DV.VehicleDialog):
        _src = inspect.getsource(_cls._import_photo)
        assert "getOpenFileName" in _src and "Supprimer le fond ?" in _src, _cls
        assert "_remove_bg_on" in _src, (_cls, "le Oui doit lancer le détourage")
        assert "RemoveBackgroundWorker" in inspect.getsource(_cls._remove_bg_on), _cls
    # SANS détourage : Décor (import direct)
    _dsrc = inspect.getsource(DD.DecorDialog._import_photo)
    assert "getOpenFileName" in _dsrc and "Supprimer le fond ?" not in _dsrc, \
        "le Décor ne doit PAS proposer le détourage"
    assert not hasattr(DD.DecorDialog, "_remove_bg_on"), "pas de BiRefNet côté Décor"
    # Headless : l'import ajoute à la galerie et active l'image ; le retour
    # BiRefNet ajoute l'image détourée ; le mock ne casse rien.
    d = tempfile.mkdtemp()
    img1 = os.path.join(d, "prop.png");   QPixmap(60, 60).save(img1)
    img2 = os.path.join(d, "prop_nobg.png"); QPixmap(60, 60).save(img2)
    dlg = DA.AccessoryDialog()
    dlg._add_gallery_image(img1, "Photo importée ✓")
    assert dlg._image_path == img1 and img1 in dlg._generated_images
    dlg._on_bg_removed(img2)
    assert dlg._image_path == img2 and img2 in dlg._generated_images
    assert len(dlg._generated_images) == 2, "la photo d'origine reste en galerie"
    dlg._on_bg_removed("")   # mode mock → statut, pas d'ajout ni de crash
    assert len(dlg._generated_images) == 2
    assert hasattr(dlg, "_btn_import_photo"), "bouton d'import absent"
    # Les 4 dialogs ont le bouton, avec un style aux VRAIES couleurs CP
    for _cls in (DA.AccessoryDialog, DH.HMCDialog, DV.VehicleDialog, DD.DecorDialog):
        _d = _cls()
        assert hasattr(_d, "_btn_import_photo"), (_cls, "bouton d'import absent")
        _ss = _d._btn_import_photo.styleSheet()
        from ui.styles import CP as _CP
        assert _CP["text_secondary"] in _ss and "{0}" not in _ss, \
            (_cls, "style du bouton import mal interpolé")


@test
def fidelite_exacte_photo_au_moteur():
    """« Fidélité exacte » (fix 2026-07-16, retour Matthieu : ne reproduisait pas
    l'objet) : la photo de référence part désormais AU MOTEUR (NB2 Edit,
    image_urls en data-URL) au lieu d'une simple description Claude de 60 mots.
    Les libellés des 4 dialogs disent le vrai fonctionnement."""
    import inspect
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import api.nano_banana as NB
    _src = inspect.getsource(NB.GenerateItemWorker._real)
    assert "_fidelity_image_url" in _src, "data-URL fidélité absente"
    assert "nano-banana-2/edit" in _src, "l'image doit partir via NB2 Edit"
    assert "Recreate the EXACT subject" in _src, "prompt d'édition fidélité absent"
    # La data-URL se prépare SANS dépendre de la clé Anthropic (l'analyse Claude
    # n'est qu'un complément) : préparation AVANT le bloc `if _nb_key:`.
    _i_url = _src.find("_fidelity_image_url = (")
    _i_key = _src.find("if _nb_key:")
    assert -1 < _i_url < _i_key, "la photo doit partir même sans clé Anthropic"
    # Libellés honnêtes dans les 4 dialogs
    import ui.dialog_accessory as DA
    import ui.dialog_hmc as DH
    import ui.dialog_vehicle as DV
    import ui.dialog_decor as DD
    for _cls in (DA.AccessoryDialog, DH.HMCDialog, DV.VehicleDialog, DD.DecorDialog):
        _d = _cls()
        _items = [_d._ref_usage_combo.itemText(i)
                  for i in range(_d._ref_usage_combo.count())]
        assert any("photo part au moteur" in t for t in _items), \
            (_cls, "libellé Fidélité exacte non mis à jour", _items)
        assert not any("reproduit l" in t or "reproduit le" in t for t in _items), \
            (_cls, "ancien libellé mensonger encore présent", _items)


if __name__ == "__main__":
    sys.exit(main())
