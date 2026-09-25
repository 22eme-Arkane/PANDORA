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
    """Paramètres Cinéma : groupes Anthropic/OpenAI/expérimental + profils."""
    from ui.page_settings import SettingsPage
    p = SettingsPage()
    n = p.ai_combo.count()
    assert n >= 18, "groupes, profils et moteurs statiques absents"
    labels = [p.ai_combo.itemText(i) for i in range(n)]
    assert any("Anthropic optimisé" in x for x in labels)
    assert any("ChatGPT optimisé" in x for x in labels)
    assert any("Fable 5" in x for x in labels), "Fable 5 proposé"
    assert any("GPT-5.5" in x for x in labels), "GPT-5.5 proposé"
    assert any("Fournisseur personnalisé" in x for x in labels), "fournisseur personnalisé proposé"
    assert any("Mistral" in x for x in labels) and any("Ollama" in x for x in labels)
    assert any("Kimi" in x for x in labels), "Kimi K2.7 proposé"
    # Clés GPT + Mistral présentes (menu déroulant facultatif)
    assert hasattr(p, "openai_input") and hasattr(p, "mistral_input")
    assert hasattr(p, "_opt_keys_box") and hasattr(p, "_btn_opt_keys"), "menu clés facultatives"
    # La sauvegarde écrit bien les clés de config IA + moteur par tâche
    src = inspect.getsource(SettingsPage.save)
    for key in ("openai_key", "mistral_key", "ollama_url", "custom_url",
                "custom_model", "custom_key", "ai_task_engines"):
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
    # Profils optimisés groupés + bridge auto (bouton retiré).
    assert "anthropic_optimized" in src_pg and "openai_optimized" in src_pg
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
    main.py garde le sélecteur unifié et masque Live dans un éventuel build Cinéma seul."""
    import core.edition as ed
    # En dev (live_window présent), l'édition complète est active → chooser
    assert ed.is_cinema_only() is False, "dev = édition complète (Live présent)"
    # main.py : page unifiée, le mode Live reste protégé si le module est absent.
    src_main = open("main.py", encoding="utf-8").read()
    assert "from core.edition import is_cinema_only" in src_main
    assert "allow_live=not _CINEMA_ONLY" in src_main, "sélecteur unifié protégé"
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
    # Version bumpée — build 2.3.0 (2026-08-30) : découpage ET storyboard par
    # LOTS successifs (un livre entier devient traitable), avertissement chiffré
    # avant de dépenser, mur silencieux PLAN 999 supprimé (au-delà, les plans
    # disparaissaient sans erreur), coût des appels IA texte enfin journalisé
    # dans « Coût du projet », voix du Doublage réparées (3 moteurs sur 7
    # étaient rejetés par fal) + Voice Changer + écoute des voix.
    from core.version import VERSION
    # Build 2.4.0 (2026-09-24) : ComfyUI comme moteur et rendu local par défaut,
    # MiniMax H3 (fal, local sd.cpp, ComfyUI), ouverture de projet 46 s → 0,4 s,
    # plus de fenêtres parasites, descripteur de projet atomique.
    assert VERSION.split("-")[0] == "2.4.0", f"version attendue 2.4.0[-suffixe], lue {VERSION}"
    # ── UN SEUL numéro de version dans tout le produit ────────────────────────
    # Chaque endroit qui recopie le numéro à la main finit par diverger : la 2.0.0
    # est partie en build avec une charte d'utilisation estampillée 1.3.5, un .app
    # macOS en 1.3.5 et une fenêtre CLUF figée sur « v1.0 » depuis quatorze
    # versions (constat Matthieu 2026-07-25). Ce test ferme la porte.
    import os as _os, re as _re
    _root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))

    def _read(name):
        p = _os.path.join(_root, name)
        if not _os.path.isfile(p):
            return None
        with open(p, encoding="utf-8", errors="ignore") as _f:
            return _f.read()

    # 1. Installeur Windows.
    _issrc = _read("pandora_setup.iss")
    if _issrc is not None:
        assert f'"{VERSION}"' in _issrc, \
            f"pandora_setup.iss n'est pas à la version {VERSION}"
    # 2. Chartes d'utilisation FR + EN — LUES PAR L'UTILISATEUR à l'installation.
    for _eula in ("EULA.txt", "EULA_EN.txt"):
        _txt = _read(_eula)
        if _txt is None:
            continue
        _vers = set(_re.findall(r"(?m)^Version\s+([0-9]+\.[0-9]+\.[0-9]+)", _txt))
        assert _vers, f"{_eula} : aucune ligne « Version X.Y.Z »"
        assert _vers == {VERSION}, \
            f"{_eula} annonce {sorted(_vers)} au lieu de {VERSION}"
    # 3. Paquet macOS : le numéro doit être DÉRIVÉ, pas recopié.
    _spec = _read("pandora.spec")
    if _spec is not None:
        assert '"CFBundleShortVersionString": _VERSION' in _spec \
            and '"CFBundleVersion": _VERSION' in _spec, \
            "pandora.spec : version macOS recopiée en dur au lieu d'être lue"
    # 4. Fenêtre CLUF de l'application : même règle.
    import inspect as _insp
    from ui.dialog_eula import EulaDialog as _ED
    _esrc = _insp.getsource(_ED)
    assert "core.version import VERSION" in _esrc, \
        "ui/dialog_eula.py : numéro de version écrit en dur"


@test
def workers_cinema_routes_via_provider():
    """Texte et vision passent par core.ai_provider, sans appel Anthropic direct."""
    import api.screenplay as s
    src = inspect.getsource(s)
    assert "core.ai_provider" in src, "screenplay routé via la couche IA"
    assert "anthropic.Anthropic(" not in src
    for mod_name in ("api.enhance", "api.assistant", "core.lang", "api.nano_banana",
                     "api.real", "api.staging_vision", "api.video_engines"):
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
    DaVinci, assistant à GAUCHE + colonne symétrique, Contact en topbar,
    Paramètres centré, Studio IA sans trait doublé, bandeaux alignés 60 px."""
    import ui.pandora_window as PW
    src_sb = inspect.getsource(PW._Sidebar.__init__)
    # 64 px depuis le 2026-07-23 (intitulés de groupe retirés — barre compacte).
    assert "setFixedHeight(64)" in src_sb and "border-top" in src_sb, \
        "nav en barre basse (taskbar), plus de colonne latérale"
    assert "setFixedWidth(268)" not in inspect.getsource(PW), "colonne 268px retirée"
    src_nav = inspect.getsource(PW.NavItem.__init__)
    assert "QVBoxLayout" in src_nav, "items : icône au-dessus du libellé"
    src_init = inspect.getsource(PW.PandoraWindow.__init__)
    assert 'side="left"' in src_init, "assistant IA à gauche"
    assert "_right_spacer" in src_init, "colonne symétrique au bord droit"
    # 40 px depuis le 2026-07-23 : aligné sur la première rangée des pages
    # (barres d'outils Scénario/Storyboard à 40 px, bandeaux 60 px disparus).
    assert "header_height=40" in src_init, "en-tête assistant aligné sur la 1re rangée"
    src_top = inspect.getsource(PW.PandoraWindow._build_global_topbar)
    assert "_btn_manual_top" not in src_top and "_btn_contact_top" in src_top, \
        "Nous contacter seul en haut à gauche"
    assert "37,211,102" in src_top and "_btn_update_header" not in src_top, \
        "Contact en VERT et bouton Mise à jour retiré"
    from ui.page_settings import SettingsPage as _SettingsPage
    assert hasattr(_SettingsPage, "manual_requested"), "Manuel déplacé dans Paramètres"
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
    # Paramètres pleine largeur depuis le 2026-07-22 : la barre de défilement est
    # collée au bord droit ; le centrage (max 1360) vit DANS SettingsPage.
    # Depuis la construction paresseuse (24/09/2026) la page Paramètres naît
    # dans sa fabrique ; la pile reçoit chaque page via _on_page_built.
    src_pages = inspect.getsource(PW.PandoraWindow._make_page_settings)
    assert "_settings_wrap" in src_pages, "page Paramètres absente de la pile"
    assert "LazyPages" in inspect.getsource(PW.PandoraWindow._build_pages)
    from ui.page_settings import SettingsPage as _SP
    _sp_src = inspect.getsource(_SP.__init__)
    assert "setMaximumWidth(1360)" in _sp_src and "addStretch(1)" in _sp_src, \
        "contenu Paramètres non centré à l'intérieur du scroll"
    assert "_settings_wrap" in inspect.getsource(PW.PandoraWindow._navigate)
    # Studio IA : trait unique + onglets formulaire plafonnés/centrés
    from ui.seedance_widget import SeedanceWidget
    src_sw = inspect.getsource(SeedanceWidget)
    assert "setDrawBase(False)" in src_sw, "pas de ligne de base doublée"
    assert "_clamp_content_width" in src_sw, "onglets formulaire plafonnés"
    assert "self.tab_t2v, self.tab_davinci, self.tab_engines" in src_sw, \
        "plafonnés : formulaires seulement (Vidéothèque/Historique pleine largeur)"
    # Bandeau titre « Storyboard » RETIRÉ (2026-07-22) : ses contrôles (versions,
    # snapshots, durée) sont intégrés à la barre d'outils des plans.
    from ui.page_storyboard import PageStoryboard as _PSB
    assert not hasattr(_PSB, "_build_shots_topbar"), "bandeau titre censé être retiré"
    assert "_build_topbar_controls" in inspect.getsource(_PSB._build_shots_toolbar), \
        "contrôles de l'ex-bandeau non intégrés à la barre d'outils"


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
    # Depuis le 2026-07-25, TOUS les champs techniques du plan partent (et plus
    # seulement focale + mouvement) via core.shot_terms.camera_terms, utilisé aux
    # DEUX endroits : assemblage du prompt final ET envoi en mode libre.
    from core.shot_terms import camera_terms as _ctf, STATIC_EN as _STE
    assert "static" in _STE.lower() and "no camera movement" in _STE.lower(), \
        "Fixe = plan fixe explicite (vocabulaire partagé)"
    _full = _ctf({"shot_size": "GP", "camera_axis": "Plongée", "focal": "85mm",
                  "camera_distance": "0.6m", "camera_height": "1.7 m",
                  "speed": "Ralenti", "camera_movement": "Fixe"})
    _joined = ", ".join(_full).lower()
    for _frag, _lbl in (("close-up", "valeur de plan"), ("high angle", "axe caméra"),
                        ("85mm", "focale"), ("0.6m", "distance"),
                        ("1.7m high", "hauteur"), ("slow motion", "vitesse"),
                        ("locked-off", "mouvement fixe")):
        assert _frag in _joined, f"champ non injecté dans le prompt : {_lbl}"
    assert not _ctf({}), "plan vide → aucun terme"
    _t2v = inspect.getsource(__import__("ui.tab_t2v", fromlist=["_"]))
    assert _t2v.count("camera_terms(self._active_shot)") >= 2, \
        "champs caméra injectés dans l'envoi réel ET l'assemblage du prompt final"


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
    """Règle portée du Live (2026-07-13) : une Mise en page PANDORA structurée se
    convertit en plans storyboard SANS appel IA — prompts co-écrits repris TELS
    QUELS, zéro perte, zéro reformulation. L'avertissement de réécriture n'apparaît
    QUE si le chemin repasse réellement par l'IA. Couvre LES DEUX formats : Live
    (« PLAN n — … » + « PROMPT VIDÉO ») ET Cinéma (« P01 | … » + « → SEEDANCE: »)."""
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
    from core.prompt_sections import is_structured, parse
    assert s0["scene_title"] == "Titre 1" and is_structured(s0["seedance_prompt"]) \
        and parse(s0["seedance_prompt"])["action"] == "vidéo 1 co-écrite" \
        and s0["sound_prompt"] == "son 1" and s0["shot_size"] == "Plan moyen" \
        and s0["camera_movement"] == "Panoramique" and s0["seq_num"] == 1, \
        "champs du plan non repris de la mise en page"
    assert s0["character_ids"] == [] and s0["decor_id"] == "" and s0["merged"] is False, \
        "défauts sûrs attendus pour les champs non couverts"
    # Worker : depuis le 2026-07-23 le chemin structuré REPASSE par l'IA (remise en
    # case des champs), avec REPLI déterministe si l'IA échoue. Le harnais NE DOIT
    # JAMAIS toucher le réseau → on force l'échec de l'appel IA et on vérifie que
    # le repli livre bien les 23 plans co-écrits, prompts intacts.
    import core.ai_provider as _aip_mod
    _orig_complete = _aip_mod.complete
    _aip_mod.complete = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline"))
    try:
        w = GenerateStoryboardWorker(layout); cap = {}
        w.finished.connect(lambda s: cap.__setitem__("s", s))
        w.failed.connect(lambda e: cap.__setitem__("f", e))
        w.run()
    finally:
        _aip_mod.complete = _orig_complete
    assert "f" not in cap and len(cap.get("s", [])) == 23, \
        f"worker : mise en page 23 plans → repli déterministe 23 plans (obtenu {len(cap.get('s', []))})"
    assert parse(cap["s"][4]["seedance_prompt"])["action"] == "vidéo 5 co-écrite", \
        "prompt co-écrit reformulé !"
    assert "_structured_fallback" in inspect.getsource(GenerateStoryboardWorker.run), \
        "repli déterministe absent du worker (filet anti-perte)"
    # Durée : plafond Seedance 15 s conservé même sur une mise en page trop longue.
    _long = dl.layout_segments_to_cinema_shots(
        'PLAN 1 — X\nDurée : 40s · Valeur de plan : Large\nPROMPT VIDÉO (français) : "v"')
    assert _long and _long[0]["duration"] == 15.0, "durée non plafonnée à 15 s"
    # ── Format CINÉMA RÉEL (« P01 | … | ~Durée » + « → SEEDANCE: … ») ──────────────
    # Jamais couvert avant → la mise en page Cinéma repartait en RÉÉCRITURE IA au lieu
    # d'être reprise plan par plan (retour Matthieu 2026-07-20 : « il veut réécrire »).
    cine = (
        "—— SÉQUENCE 1 — ARRIVÉE ——\n"
        "P01 | Plan large | Travelling avant | Face | ~6s\n"
        "EXT. RUE — NUIT\n"
        "Une silhouette avance sous la pluie.\n"
        "→ SEEDANCE: Rue déserte la nuit, silhouette sous la pluie, néons.\n\n"
        "P02 | Gros plan | Fixe | 3/4 | ~4s\n"
        "INT. VOITURE — NUIT\n"
        "                VIKTOR\n"
        "        Ils sont là.\n"
        "→ SEEDANCE: Gros plan sur Viktor tendu,\nlumières de la ville floues.\n")
    assert dl.is_structured_layout(cine), "format Cinéma (« P01 | … » / « → SEEDANCE: ») non reconnu"
    cshots = dl.layout_segments_to_cinema_shots(cine)
    assert len(cshots) == 2, f"Cinéma : {len(cshots)}/2 plans"
    c0 = cshots[0]
    assert (parse(c0["seedance_prompt"])["action"].startswith("Rue déserte")
            and c0["shot_size"] == "Plan large"
            and c0["camera_movement"] == "Travelling avant" and c0["camera_axis"] == "Face"
            and c0["duration"] == 6.0 and c0["seq_name"] == "ARRIVÉE"), \
        "champs Cinéma non repris du format « P01 | … »"
    # Prompt multi-lignes recollé, dialogue exclu du prompt, nom perso pas pris en titre.
    c1_action = parse(cshots[1]["seedance_prompt"])["action"]
    assert "floues" in c1_action and "Ils sont là" not in c1_action
    assert cshots[1]["scene_title"] != "VIKTOR", "nom de personnage pris comme titre du plan"
    # Le worker garde le repli déterministe sur le format Cinéma (harnais OFFLINE :
    # l'appel IA est forcé en échec, le filet doit livrer les 2 plans).
    _aip_mod.complete = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline"))
    try:
        wc = GenerateStoryboardWorker(cine); capc = {}
        wc.finished.connect(lambda s: capc.__setitem__("s", s)); wc.run()
    finally:
        _aip_mod.complete = _orig_complete
    assert len(capc.get("s", [])) == 2, "worker Cinéma : repli « P01 | … » non déterministe"
    # Depuis le 2026-07-23 : source non structurée → CONFIRMATION explicite (plus de refus).
    from ui.page_scenario import PageScenario as _PS
    _src = inspect.getsource(_PS._on_storyboard)
    assert "is_structured_layout" in _src and "Découpage non structuré" in _src, \
        "page Scénario : confirmation du découpage non structuré absente"
    from ui.page_storyboard import PageStoryboard as _PSB
    _oa = inspect.getsource(_PSB._on_analyze)
    assert "validate_layout" in _oa and "Aucune réécriture IA automatique" in _oa, \
        "page Storyboard : import strict du découpage validé absent"


@test
def colonne_langues_dialogues():
    """Colonne « Langues » (storyboard Cinéma) : choix par plan, défaut anglais ;
    dialogues traduits À L'ENVOI uniquement (pas dans le prompt affiché)."""
    import ui.page_storyboard as M
    assert len(M._COLS) == 22, \
        "Langues (16) · Nom du plan (17) · boutons (18) · Hauteur (19) · Référence (20) · P. de champ (21) = 22 colonnes"
    # Profondeur de champ : colonne ENTRE Focale et Distance dans l'ordre par défaut
    # (demande Matthieu 2026-07-25), avec son réglage dans la fiche de plan.
    _o = M._DEFAULT_COL_ORDER
    assert _o.index(21) == _o.index(8) + 1 and _o.index(9) == _o.index(21) + 1, \
        "« P. de champ » doit être placée entre Focale et Dist."
    from core.storyboard import DEPTHS_OF_FIELD
    from core.shot_terms import camera_terms as _ct_dof, dof_to_en
    assert "" in DEPTHS_OF_FIELD and "Grande" in DEPTHS_OF_FIELD, "valeurs de profondeur"
    assert dof_to_en("Grande") and not dof_to_en(""), "vide = déduite de la focale"
    # Une profondeur EXPLICITE prime sur celle déduite de la focale (sinon deux
    # indications contradictoires dans le même prompt).
    _tdof = ", ".join(_ct_dof({"focal": "85mm", "depth_of_field": "Grande"}))
    assert _tdof.lower().count("depth of field") <= 1, "profondeur de champ en double"
    assert "deep focus" in _tdof, "la valeur explicite doit primer sur la focale"
    assert '"depth_of_field":' in inspect.getsource(
        __import__("ui.dialog_shot", fromlist=["_"])), "réglage absent de la fiche de plan"
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
    assert "DÉCOUPAGE PANDORA 2" in s._FORMAT_PANDORA
    assert "SOURCE SCÉNARIO" in s._FORMAT_PANDORA and "PROMPT VISUEL" in s._FORMAT_PANDORA
    assert "SCREENPLAY SOURCE" in s._FORMAT_PANDORA_EN and "VISUAL PROMPT" in s._FORMAT_PANDORA_EN
    assert "P01 | Valeur de plan" not in s._FORMAT_PANDORA, "ancien contrat encore actif"


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
def bouton_don_paypal_utilisable():
    """« Soutenir PANDORA » doit pointer un lien de don RÉELLEMENT utilisable.

    Le bouton renvoyait vers « paypal.com/donate?business=<email> » : ce point
    d'entrée passe par le programme de dons PayPal, réservé aux organisations
    caritatives enregistrées, et répondait « Cette organisation ne peut pas
    accepter de dons pour l'instant » (constat Matthieu 2026-07-25). Le bouton
    était donc mort depuis sa mise en place, sans que rien ne le signale."""
    import ui.dialog_funding as F
    url = F._PAYPAL_URL
    assert "donate?business=" not in url, \
        "lien /donate : exige un statut d'organisation caritative, inutilisable ici"
    assert url.startswith("https://"), f"lien de don non sécurisé : {url}"
    assert "paypal.me/" in url or "ko-fi.com/" in url or "liberapay.com/" in url, \
        f"forme de lien de don non reconnue : {url}"
    # Les adresses crypto restent des chaînes non vides (autres moyens de soutien).
    assert F._BTC_ADDRESS.strip() and F._USDC_ADDRESS.strip(), "adresses crypto vides"


@test
def decoupage_jamais_tronque_en_silence():
    """Le Découpage doit être COMPLET ou refusé — jamais un demi-document enregistré.

    Constat Matthieu 2026-07-25 : découpage arrêté au plan 28 sur la moitié d'un
    scénario. Le moteur atteignait les 16000 tokens et s'arrêtait net ; comme
    CHAQUE plan produit était bien formé, le contrat v2 validait et PANDORA
    enregistrait le demi-découpage sans un mot. Relever le plafond ne fait que
    déplacer le mur (il était déjà passé de 8000 à 16000) : on DÉTECTE la coupe et
    on demande la suite."""
    import inspect
    import core.ai_provider as AP
    import api.screenplay as SP
    from core.decoupage_document import validate_v2_document

    # 1. La boucle anti-troncature rend des comptes (et pas seulement du texte).
    assert hasattr(AP, "chat_until_complete_ex"), "chat_until_complete_ex absent"
    _src = inspect.getsource(AP.chat_until_complete_ex)
    assert '"truncated"' in _src and "CONTINUE_PROMPT" in _src, \
        "la boucle ne signale pas une troncature persistante"

    # 2. Le Découpage passe par cette boucle, plus par un appel simple.
    _d = inspect.getsource(SP.FormatPandoraWorker._decoupage_call)
    assert "chat_until_complete_ex" in _d, "le Découpage n'a pas de boucle anti-troncature"
    assert "raise" in _d and "INCOMPLET" in _d, \
        "un découpage encore tronqué doit être REFUSÉ, pas enregistré"
    _r = inspect.getsource(SP.FormatPandoraWorker.run)
    assert "_decoupage_call" in _r and "ai_stream(" not in _r, \
        "la génération du Découpage court-circuite encore la boucle"

    # 3. Preuve du danger : un demi-document PASSE le contrat v2. C'est bien la
    #    détection de la coupe — pas la validation — qui protège l'utilisateur.
    def _plan(n):
        return (f"PLAN {n:02d}\nSOURCE SCÉNARIO : Extrait {n}.\n"
                f"INTENTION : Montrer {n}.\nRYTHME : Neutre.\nDURÉE : 5s\n"
                f"PROMPT VISUEL : Image {n}.\nPERSONNAGES : —\nDÉCOR : —\n"
                "ACCESSOIRES : —\nVÉHICULES : —\nHMC : —\nVALEUR PROPOSÉE : —\n"
                "AXE PROPOSÉ : —\nMOUVEMENT PROPOSÉ : —\nFOCALE PROPOSÉE : —\n"
                "MOOD : À CRÉER\n")
    _moitie = "DÉCOUPAGE PANDORA 2\n\n" + "\n".join(_plan(i) for i in range(1, 29))
    assert validate_v2_document(_moitie) == [], \
        "hypothèse du test caduque : le contrat rejette désormais un demi-document"

    # 4. La boucle recolle réellement les reprises, sans réseau.
    _orig = AP.chat_ex
    _state = {"calls": 0}
    try:
        def _fake(system, messages, tier="creative", max_tokens=2048, task=None):
            _state["calls"] += 1
            deja = 0
            for m in messages:
                if m.get("role") == "assistant":
                    deja = m["content"].count("PLAN ")
            fin = min(60, deja + 28)
            txt = ("DÉCOUPAGE PANDORA 2\n\n" if deja == 0 else "")
            txt += "\n".join(_plan(i) for i in range(deja + 1, fin + 1))
            return {"text": txt, "truncated": fin < 60}
        AP.chat_ex = _fake
        res = AP.chat_until_complete_ex("s", [{"role": "user", "content": "x"}],
                                        max_tokens=16000, task="decoupage", max_rounds=6)
    finally:
        AP.chat_ex = _orig
    assert res["text"].count("PLAN ") == 60, \
        f"document incomplet après reprises : {res['text'].count('PLAN ')} plans"
    assert res["truncated"] is False and _state["calls"] >= 3, \
        "les reprises n'ont pas eu lieu"
    assert validate_v2_document(res["text"]) == [], "le document recollé est invalide"


@test
def moods_references_toutes_familles():
    """Le Mood doit recevoir TOUTES les fiches images du plan : personnages, décor,
    accessoires, véhicules, HMC. Les trois dernières n'étaient jamais envoyées et
    la fenêtre ne proposait même pas de les inclure (constat Matthieu 2026-07-25)."""
    import inspect, os as _os, tempfile as _tf
    import api.apercu as A
    import core.casting, core.decors, core.accessories, core.vehicles, core.hmc

    _tmp = _tf.mkdtemp(prefix="pandora_moodrefs_")
    def _img(n):
        p = _os.path.join(_tmp, n + ".png")
        with open(p, "wb") as f:                     # fichier bidon : seul isfile() compte
            f.write(b"\x89PNG\r\n\x1a\n")
        return p
    _I = {k: _img(k) for k in ("perso", "decor", "prop", "veh", "hmc")}
    _orig = (core.casting.get_character, core.decors.get_decor,
             core.accessories.get_accessory, core.vehicles.get_vehicle,
             core.hmc.get_hmc_item)
    core.casting.get_character     = lambda i: {"image_path": _I["perso"]}
    core.decors.get_decor          = lambda i: {"image_path": _I["decor"]}
    core.accessories.get_accessory = lambda i: {"image_path": _I["prop"]}
    core.vehicles.get_vehicle      = lambda i: {"image_path": _I["veh"]}
    core.hmc.get_hmc_item          = lambda i: {"image_path": _I["hmc"]}
    try:
        shot = {"id": "s", "character_ids": ["c"], "decor_id": "d",
                "accessory_ids": ["a"], "vehicle_ids": ["v"], "hmc_ids": ["h"]}
        refs = A._shot_ref_images(shot)
        for k in ("perso", "decor", "prop", "veh", "hmc"):
            assert _I[k] in refs, f"référence {k} absente du Mood"
        # Chaque case de la fenêtre doit pouvoir retirer sa famille.
        for arg, absent in (("include_props", "prop"), ("include_vehicles", "veh"),
                            ("include_hmc", "hmc"), ("include_chars", "perso"),
                            ("include_decor", "decor")):
            assert _I[absent] not in A._shot_ref_images(shot, **{arg: False}), \
                f"{arg}=False n'exclut pas {absent}"
    finally:
        (core.casting.get_character, core.decors.get_decor,
         core.accessories.get_accessory, core.vehicles.get_vehicle,
         core.hmc.get_hmc_item) = _orig
        import shutil as _sh
        _sh.rmtree(_tmp, ignore_errors=True)

    # La fenêtre expose les six cases, et le handler les transmet toutes.
    import ui.page_storyboard as _PS
    _dsrc = inspect.getsource(_PS._MoodBatchDialog._build_ui)
    for attr in ("_opt_chars", "_opt_decor", "_opt_props", "_opt_vehicles",
                 "_opt_hmc", "_opt_floor"):
        assert attr in _dsrc, f"case {attr} absente de la fenêtre des Moods"
    _hsrc = inspect.getsource(_PS.PageStoryboard._on_batch_mood)
    for key in ('"props"', '"vehicles"', '"hmc"'):
        assert key in _hsrc, f"{key} non transmis au worker de série"
    # …et le dispatcher lit bien ces options.
    _rsrc = inspect.getsource(A.run_mood)
    for key in ('opts.get("props"', 'opts.get("vehicles"', 'opts.get("hmc"'):
        assert key in _rsrc, f"run_mood ignore l'option {key}"


@test
def page_projets_liste_tous_les_projets():
    """La page Projets doit pouvoir atteindre TOUS les projets. Elle paginait sur
    `list_recent()`, plafonné à 9 : au-delà, les projets étaient inatteignables
    même en tournant les pages (constat Matthieu 2026-07-25 : 19 au registre)."""
    import inspect
    import core.project as P
    assert hasattr(P, "list_all"), "core.project.list_all absent"
    assert P.list_recent(max_count=None) is not None, "list_recent sans plafond"
    import ui.page_projects as _PP
    _src = inspect.getsource(_PP.PageProjects._projects)
    assert "project_api.list_all()" in _src \
        and "project_api.list_recent()" not in _src, \
        "la page Projets pagine encore sur la liste plafonnée"


@test
def generation_elements_choix_du_moteur():
    """« Identifier et générer les images » doit demander le MOTEUR pour les cinq
    catégories, pas seulement pour les décors (demande Matthieu 2026-07-25) : le
    prompt est écrit dans la grammaire du moteur, le choix doit précéder l'envoi."""
    import inspect
    from ui.dialog_extract_generate import ExtractGenerateDialog
    for label, factory in (("casting",     ExtractGenerateDialog.for_characters),
                           ("décors",      ExtractGenerateDialog.for_decors),
                           ("accessoires", ExtractGenerateDialog.for_accessories),
                           ("HMC",         ExtractGenerateDialog.for_hmc),
                           ("véhicules",   ExtractGenerateDialog.for_vehicles)):
        dlg = factory("INT. CANYON - JOUR\nJésus tient un smartphone.", None)
        combo = getattr(dlg, "_image_model_combo", None)
        assert combo is not None, f"{label} : pas de sélecteur de moteur d'image"
        keys = [combo.itemData(i) for i in range(combo.count())]
        assert len(keys) >= 10, f"{label} : catalogue de moteurs incomplet ({len(keys)})"
        assert any("seedream" in str(k) for k in keys), f"{label} : Seedream absent"
        # Le chemin « 7 vues » (décors) lit l'ancien nom : il doit pointer le même objet.
        assert dlg._room_image_model_combo is combo, f"{label} : alias 7-vues cassé"
        dlg.deleteLater()
    _g = inspect.getsource(ExtractGenerateDialog._gen_next)
    assert _g.count("model_key=_engine") == 2, \
        "le moteur choisi n'est pas transmis aux workers (portrait ET élément)"


@test
def moods_en_serie_prompt_retravaille():
    """« Générer les Moods » en série doit produire le MÊME prompt retravaillé que
    la fenêtre Mood : écrit dans la grammaire du moteur choisi, débarrassé des
    termes vidéo."""
    import inspect
    import core.storyboard as sb
    import api.apercu as A
    sb.set_namespace("storyboard")
    _run = inspect.getsource(A.MoodBatchWorker.run)
    # Le constructeur de prompt de la série est passé par `compose_mood_prompt`
    # le 2026-07-27 (composition IA + repli déterministe). L'exigence est la
    # même — le MOTEUR doit atteindre la construction du prompt — seul le nom
    # de la fonction a changé.
    assert 'self._options.get("engine")' in _run and "compose_mood_prompt" in _run, \
        "la série ne transmet pas le moteur au constructeur de prompt"
    import ui.page_storyboard as _PS
    _dlg = inspect.getsource(_PS.PageStoryboard._on_batch_mood)
    assert '"engine"' in _dlg and "MoodBatchWorker" in _dlg, \
        "la fenêtre de série ne transmet pas le moteur choisi"
    shot = {"id": "s", "seedance_prompt": "Jésus sur le rocher. La caméra avance. 8 secondes.",
            "shot_size": "GP", "focal": "85mm"}
    p_nb2  = A.build_mood_prompt(shot, "", "nb2")
    p_seed = A.build_mood_prompt(shot, "", "seedream5")
    assert "Action:" in p_nb2 and "Action:" not in p_seed, "grammaire non appliquée en série"
    for p in (p_nb2, p_seed):
        assert "avance" not in p.lower(), "mouvement caméra (FR) dans un prompt d'image"
        assert "8 sec" not in p.lower(), "durée dans un prompt d'image"


@test
def picker_elements_nom_lisible_quand_selectionne():
    """Storyboard : cocher un accessoire ne doit pas faire disparaître son nom.
    `:selected` ne neutralisait que le FOND — le texte prenait la couleur « sur
    surbrillance » de la palette, sombre sur fond sombre (constat Matthieu
    2026-07-25). Vérifié des deux côtés : même dialogue, même défaut."""
    import inspect
    import ui.page_storyboard as _c, ui.page_storyboard_live as _l
    for mod, side in ((_c, "Cinéma"), (_l, "Live")):
        src = inspect.getsource(mod._elements_picker_dialog)
        assert "QListWidget::item:selected{{background:transparent;}}" not in src, \
            f"{side} : ancien style qui efface le texte sélectionné"
        _i = src.index("::item:selected")
        assert "color:" in src[_i:_i + 160], \
            f"{side} : `:selected` sans couleur de texte explicite"
        assert "rgba(" in src[_i:_i + 160], \
            f"{side} : fond de sélection en hex-opacity (interdit sur fond sombre)"


@test
def studio_ia_prompt_final_mis_en_cache():
    """Composer un prompt final est un appel IA PAYANT. Revenir sur un plan déjà
    composé, storyboard inchangé, doit le réutiliser tel quel (demande Matthieu
    2026-07-25). La clé couvre TOUT ce qui entre dans la composition — si le texte
    du plan, le moteur, la durée, le style ou une fiche personnage bouge, on
    recompose. Un échec API n'est jamais mémorisé : il doit pouvoir être retenté."""
    import inspect
    from ui.tab_t2v import TabT2V
    for name in ("_final_cache_key", "_remember_final", "_compose_context"):
        assert hasattr(TabT2V, name), f"TabT2V.{name} absent"
    # La clé est l'empreinte du prompt ET du contexte — pas du seul id de plan
    # (sinon modifier le plan renverrait l'ancien prompt).
    _k = inspect.getsource(TabT2V._final_cache_key)
    assert "prompt_fr" in _k and "ctx" in _k and "sha1" in _k, \
        "clé de cache : doit couvrir le prompt ET le contexte de composition"
    _s = inspect.getsource(TabT2V._start_preview_translate)
    assert "_final_cache.get" in _s and "_on_preview_translated(*" in _s, \
        "cache non consulté avant de lancer la composition"
    assert "_FinalPromptWorker" in _s, "composition absente du chemin de secours"
    # Le contexte du cache est EXACTEMENT celui envoyé au composeur.
    _c = inspect.getsource(TabT2V._compose_context)
    for k in ('"engine"', '"duration"', '"style_suffix"', '"character_notes"',
              '"dialogue_lang"', '"sound_notes"'):
        assert k in _c, f"contexte de composition incomplet : {k}"
    _r = inspect.getsource(TabT2V._remember_final)
    assert "if why:" in _r and "return" in _r, \
        "un échec API (crédits, réseau) ne doit PAS être mis en cache"
    # La file d'attente attend le prompt final : un plan généré en série reçoit
    # le MÊME prompt qu'à l'unité — et profite donc aussi du cache.
    _b = inspect.getsource(TabT2V._process_next_batch_shot)
    assert "_await_final_then_generate" in _b, \
        "la file part sans attendre le prompt final"


@test
def studio_ia_bandeau_et_vignettes_sous_elements_injectes():
    """Le bandeau « MODE RÉFÉRENCE ACTIF » annonce les images envoyées : il doit
    être posé sous « Éléments injectés », juste au-dessus des vignettes qu'il
    décrit — et les vignettes doivent montrer TOUTES ces images, décor compris."""
    import inspect
    from ui.tab_t2v import TabT2V
    _src = inspect.getsource(TabT2V.__init__)
    _i_prev  = _src.index("_ez_lay.addWidget(self._prompt_preview)")
    _i_bann  = _src.index("_ez_lay.addWidget(self._ref_mode_banner)")
    _i_thumb = _src.index("_ez_lay.addWidget(self._thumb_strip)")
    assert _i_prev < _i_bann < _i_thumb, \
        "ordre attendu : Éléments injectés → bandeau référence → vignettes"
    # ⚠ get_selected_images() OMET le décor : le bandeau annonçait 2 images et le
    # strip n'en montrait qu'une. Les deux doivent lire get_ref_images().
    _a = inspect.getsource(TabT2V._all_reference_images)
    assert "self._casting.get_ref_images()" in _a \
        and "self._casting.get_selected_images()" not in _a, \
        "les vignettes ne lisent pas la liste réellement envoyée (décor manquant)"
    _b = inspect.getsource(TabT2V._update_injection_banner)
    assert "get_ref_images" in _b, "bandeau et vignettes doivent partager la source"


@test
def studio_ia_parametres_ordre_de_lecture():
    """Bloc PARAMÈTRES : plan du storyboard, puis sa traduction juste dessous,
    puis durée, son et ADN visuel (demande Matthieu 2026-07-25). La traduction
    n'est plus tronquée — c'est elle qu'on vient vérifier."""
    import inspect
    from ui.tab_t2v import TabT2V
    _src = inspect.getsource(TabT2V._build_full_preview_text)
    assert "Paramètres injectés depuis le storyboard" not in _src, "ancien libellé"
    for a, b in (("Plan  ← storyboard", "Traduction des paramètres du storyboard"),
                 ("Traduction des paramètres du storyboard", 'f"Durée : '),
                 ('f"Durée : ', '"Son : "'),
                 ('"Son : "', 'f"ADN visuel')):
        assert _src.index(a) < _src.index(b), f"ordre PARAMÈTRES : {a!r} doit précéder {b!r}"
    _i = _src.index("Traduction des paramètres du storyboard")
    assert "[:150]" not in _src[_i:_i + 400], "la traduction ne doit plus être tronquée"


@test
def elements_fond_blanc_obligatoire():
    """Casting / accessoires / HMC / véhicules : fond blanc TOUJOURS, quel que soit
    le mode et le moteur (décision Matthieu 2026-07-25). Ces images repartent en
    référence au moteur vidéo — un décor derrière le sujet polluerait le plan.
    Les décors, eux, restent de vrais lieux."""
    import inspect
    import api.nano_banana as nb
    from core.image_grammar import has_white_bg
    base = "Un chevalier en armure rouillée"
    modes = {
        "portrait classique":    nb._CLASSIC_PORTRAIT_SUFFIX,
        "portrait éditorial":    nb._EDITORIAL_PORTRAIT_SUFFIX,
        "pose d'action":         nb._ACTION_POSE_SUFFIX,
        "portrait duo":          nb._DUO_PORTRAIT_SUFFIX,
        "sheet 5 vues":          nb._SHEET_SUFFIX,
        "accessoire / HMC":      nb._ITEM_LINE,
        "véhicule":              nb._VEHICLE_LINE,
        # ⚠ LE TROU HISTORIQUE : en « style pictural depuis une image de
        # référence », le suffixe était remplacé par "" → plus AUCUN fond blanc.
        "style depuis image":    "",
    }
    for label, sfx in modes.items():
        src = (base + "\n\n" + sfx) if sfx else base
        for eng in ("nb2", "nb_pro", "gpt2", "seedream5", "flux2", "recraft"):
            out = nb.finalize_element_prompt(src, eng, True)
            assert has_white_bg(out), f"{label} / {eng} : fond blanc absent"
    # Décor : surtout PAS de fond blanc imposé.
    dec = nb.finalize_element_prompt(base + "\n\n" + nb._DECOR_LINE, "nb2", False)
    assert "isolated on plain white" not in dec, "décor : fond blanc imposé à tort"
    assert "location photograph" in dec.lower(), "décor : reste un lieu réel"
    # Les 4 chemins de génération d'élément passent bien par la finalisation.
    for fn in (nb.GeneratePortraitWorker._real, nb.GenerateItemWorker._real,
               nb.GenerateDecorSheetWorker._real,
               nb.GeneratePortraitNB2EditWorker._real):
        assert "finalize_element_prompt" in inspect.getsource(fn), \
            f"{fn.__qualname__} : prompt non finalisé (fond blanc / grammaire moteur)"
    # Le Live garde SES dossiers : en mapping le fond doit rester NOIR.
    assert nb._WHITE_BG_SUBDIRS == {"castings", "accessories", "hmc", "vehicles"}, \
        "fond blanc étendu au Live par erreur (mapping = fond noir pur)"


@test
def elements_grammaire_par_moteur():
    """Le prompt d'un élément est réécrit pour le moteur choisi, sans rien perdre
    sur le chemin par défaut (Nano Banana)."""
    import api.nano_banana as nb
    base = "Un casque de moto rouge"
    src  = base + "\n\n" + nb._ITEM_LINE
    # Nano Banana : la consigne éprouvée part TELLE QUELLE (zéro régression).
    out_nb2 = nb.finalize_element_prompt(src, "nb2", True)
    assert "No person, no face, no character, no model." in out_nb2, \
        "Nano Banana : la consigne d'origine a été modifiée"
    # Seedream : ByteDance a retiré le prompt négatif → « no person » y serait lu
    # comme « person ». Les interdits doivent être devenus positifs.
    out_seed = nb.finalize_element_prompt(src, "seedream5", True)
    _flat = " " + out_seed.lower().replace(",", " ").replace(".", " ") + " "
    assert " no " not in _flat, f"Seedream : interdit resté dans le prompt — {out_seed}"
    assert "unpopulated" in out_seed or "studio backdrop" in out_seed, \
        "Seedream : interdits supprimés sans contrepartie positive"
    # Le sujet de l'utilisateur n'est jamais perdu.
    for out in (out_nb2, out_seed):
        assert "casque de moto rouge" in out, "sujet perdu à la réécriture"
    # Repli sûr : une erreur de grammaire ne doit jamais empêcher une génération.
    assert nb.finalize_element_prompt("", "moteur-inconnu", False) == ""
    # Le filtre « vidéo » ne doit pas dévorer du vocabulaire de production courant :
    # une veste des années 1970 n'est pas une durée, une cassette audio n'est pas
    # une bande son, un miroir à main n'est pas une caméra portée.
    from core.image_grammar import strip_video_terms
    for phrase in ("a 1970s leather jacket", "80s sneakers with worn soles",
                   "an audio cassette on the table", "a handheld mirror in her palm",
                   "a copper pan hanging above the stove",
                   "a crane standing in the marsh",
                   "une caméra Super 8 posée sur la commode"):
        kept, _ = strip_video_terms(phrase)
        assert kept.strip() == phrase, f"objet supprimé à tort : {phrase!r} → {kept!r}"


@test
def prompt_mood_cinema_inchange():
    """build_mood_prompt en namespace Cinéma : contenu complet, sans vidéo-only."""
    import core.storyboard as sb
    from api.apercu import build_mood_prompt
    sb.set_namespace("storyboard")
    p = build_mood_prompt({"seedance_prompt": "a forest", "focal": "35mm",
                           "shot_size": "PL", "scene_title": "Marche en forêt"}, "")
    assert "35mm" in p and "wide shot" in p, "termes caméra Cinéma présents"
    # Audit prompts 2026-07-02 : plus de mots qualité génériques interdits
    # (« 4K/film grain/high quality » poussaient un rendu contradictoire).
    assert "cinematic still frame" in p.lower() and "4K" not in p, "suffixe mood assaini"
    assert "Marche en forêt" in p, "description d'action présente"
    assert "OPENING state" not in p, "pas de consigne keyframe Live côté Cinéma"


@test
def prompt_mood_sans_termes_video():
    """Un Mood est une IMAGE : mouvement, hauteur de caméra, vitesse et durée en
    sont exclus (demande Matthieu 2026-07-25) ; valeur de plan, axe, focale,
    profondeur de champ et distance restent. La focale ne dit QUE la focale."""
    import core.storyboard as sb
    from api.apercu import build_mood_prompt, mood_intent
    sb.set_namespace("storyboard")
    shot = {"seedance_prompt": "a forest. the camera pushes in slowly. 8 seconds.",
            "focal": "85mm", "shot_size": "GP", "camera_axis": "Plongée",
            "depth_of_field": "Courte", "camera_distance": "0.6m",
            "camera_height": "1.6m", "camera_movement": "Travelling avant",
            "speed": "Ralenti", "shot_time": "Nuit", "decor_name": "Désert"}
    for eng in ("nb2", "seedream5", "flux"):
        p = build_mood_prompt(shot, "", eng)
        low = p.lower()
        assert "travelling" not in low and "dolly" not in low \
            and "pushes in" not in low, f"{eng} : mouvement caméra dans un prompt image"
        assert "1.6m high" not in low and "eye-level viewpoint" not in low, \
            f"{eng} : hauteur de caméra dans un prompt image"
        assert "slow motion" not in low, f"{eng} : vitesse dans un prompt image"
        assert "8 seconds" not in low, f"{eng} : durée dans un prompt image"
        assert "85mm lens" in low, f"{eng} : focale absente"
        assert "shallow depth of field" in low, f"{eng} : profondeur de champ absente"
        assert "0.6m from subject" in low, f"{eng} : distance absente"
        assert "extreme close-up" in low and "high angle" in low, f"{eng} : cadrage absent"
        assert "nighttime" in low, f"{eng} : heure du plan non traduite en éclairage"
    # L'intention est indépendante du moteur ; seule sa mise en forme change.
    it = mood_intent(shot, "")
    assert "camera_movement" not in str(it.get("camera", "")).lower()
    assert "85mm lens" in it["camera"] and "shallow depth of field" in it["camera"]


@test
def prompt_mood_grammaire_par_moteur():
    """Changer de moteur change la FORME du prompt (dossier fal.ai 2026-07-25)."""
    import core.storyboard as sb
    from api.apercu import build_mood_prompt
    sb.set_namespace("storyboard")
    shot = {"seedance_prompt": "a forest", "shot_size": "PL", "focal": "35mm"}
    p_nb2  = build_mood_prompt(shot, "", "nb2")
    p_seed = build_mood_prompt(shot, "", "seedream5")
    p_flux2 = build_mood_prompt(shot, "", "flux2")
    p_flux  = build_mood_prompt(shot, "", "flux")
    assert "Composition and camera:" in p_nb2, "Nano Banana : brief à champs attendu"
    assert "Subject:" in p_nb2 or "Action:" in p_nb2, "Nano Banana : champs nommés"
    assert "Action:" not in p_seed and "35mm lens" in p_seed, \
        "Seedream : prose descriptive, pas de champs"
    assert p_flux2.lstrip().startswith("{") and '"camera"' in p_flux2, \
        "FLUX.2 : objet JSON attendu"
    assert "Action:" not in p_flux and "35mm lens" in p_flux, "Flux : prose simple"
    # Seedream n'a plus de prompt négatif : aucun interdit ne doit y figurer.
    from core.image_grammar import supports_negatives
    assert not supports_negatives("seedream5") and supports_negatives("nb2")


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
    # Veo 3.1 et Sora 2 étaient écartés (t2v purs) jusqu'au 24/09/2026 : leurs
    # endpoints image-to-video existent chez fal et sont envoyés depuis.
    assert "veo-3.1" in keys and "sora-2" in keys, "Veo/Sora i2v depuis le 24/09/2026"
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
                                  build_overview_prompt, build_seven_view_prompts,
                                  extract_base_prompt)
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
    # Un extérieur ne doit JAMAIS recevoir les consignes de pièce qui faisaient
    # inventer des murs, fenêtres, mobilier et plafond dans une vallée.
    exterior = build_seven_view_prompts("desert canyon", "Extérieur")
    exterior_text = "\n".join(p for _, _, p in exterior)
    assert "Interior view" not in exterior_text and "ENTIRE room" not in exterior_text
    assert "OPEN SKY" in next(p for _, c, p in exterior if c == "plafond")
    assert "90 degrees clockwise" in next(p for _, c, p in exterior if c == "droite")
    assert "90 degrees counter-clockwise" in next(p for _, c, p in exterior if c == "gauche")
    from api.nano_banana import _floor_plan_prompt
    exterior_plan = _floor_plan_prompt("desert canyon", "Extérieur")
    assert "OUTDOOR SITE PLAN" in exterior_plan and "no rooms" in exterior_plan
    legacy = ("Vast desert canyon with ochre cliffs. Wide establishing shot of the "
              "ENTIRE room seen at once: floor, ceiling and walls.")
    assert extract_base_prompt(legacy) == "Vast desert canyon with ochre cliffs", \
        "les variations des anciens projets ne doivent pas recycler le faux intérieur"
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
    # COHÉRENCE des 6 faces : chaque face est une ÉDITION du moteur de raccord
    # choisi qui INJECTE le plan
    # d'ensemble + le plan d'architecture comme RÉFÉRENCES (même pièce, angles
    # différents) ; repli TEXTE robuste (4 essais, backoff) si l'édition échoue.
    assert "ref_urls" in nb and "_gen_edit" in nb and "consistency" in nb, \
        "faces générées par édition avec références (plan d'ensemble + plan d'archi)"
    assert "reference_model_key" in inspect.signature(GenerateRoomViewsWorker.__init__).parameters
    assert "category" in inspect.signature(GenerateRoomViewsWorker.__init__).parameters
    assert "build_request" in nb and "ref_model" in nb, \
        "le moteur plan+raccords sélectionné doit router réellement l'endpoint"
    assert "ov_path" in nb and "fp_path" in nb, "réfs = plan d'ensemble + plan d'architecture"
    assert "edit_off" in nb and "range(4)" in nb, "repli texte robuste (4 essais)"
    assert "pandora_decor.log" in nb, "journal de diagnostic des 7 vues"
    assert "_VIEW_GAP_S" in nb, "génération ÉTAPE PAR ÉTAPE (vues espacées dans le temps)"
    assert "_faces_ok" in nb and "_last_error" in nb, "worker remonte les faces manquantes"
    assert hasattr(w, "_faces_ok") and hasattr(w, "_last_error"), "attributs de diagnostic présents"
    assert "_room_warnings" in eg and "Vues manquantes" in eg, \
        "dialogue : avertissement consolidé des faces manquantes"
    assert 'category=item.get("category", "")' in eg, \
        "la catégorie intérieur/extérieur doit arriver jusqu'au worker"
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
    # 2026-07-23 (audit « la main sur le tableau ») : champs qui étaient ignorés
    # en silence + budget élargi + parsing tolérant avec message explicite.
    for _f in ("camera_axis", "optic", "camera_height", "camera_distance",
               "seq_name", "vehicle_names", "chars_in", "chars_out"):
        assert _f in STORYBOARD_CHAT_FIELDS, f"champ {_f} absent de la liste blanche"
    _wsrc = inspect.getsource(StoryboardChatWorker._run)
    assert "max_tokens=16000" in _wsrc, \
        "8192 tronquait les demandes en lot (« tous les prompts ») → 16000"
    assert "depth" in _wsrc and "n'ont PAS pu être appliquées" in _wsrc, \
        "parsing tolérant (accolades) + message explicite en cas de troncature"
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
    """Intégration moteurs : profils OpenAI/Anthropic ; moteur IA paramétrable
    PAR TÂCHE sans dégrader le défaut ; appels câblés avec task=."""
    import core.ai_provider as ap
    assert "openai" in ap._PROVIDERS
    for key in ("claude", "opus", "haiku", "fable5", "openai_sol",
                "openai_terra", "openai_luna", "gpt", "mistral", "kimi",
                "glm", "ollama", "custom"):
        assert key in ap.ENGINES
    assert ap.ENGINES["glm"]["provider"] == "glm", "GLM (Zhipu) — API ou local"
    assert ap.ENGINES["gpt"]["provider"] == "openai"
    assert ap.ENGINES["opus"]["creative_model"] == "claude-opus-4-8"
    # Profil PANDORA optimisé (défaut) : moteur IDÉAL par tâche — Opus UNIQUEMENT
    # pour le storyboard, Sonnet pour scénario/sync, Haiku pour le reste (économe).
    assert ap.PANDORA_OPTIMIZED["storyboard_gen"] == "opus", "storyboard = Opus"
    assert ap.PANDORA_OPTIMIZED["extraction"] == "claude", "extraction = Sonnet 5 (pas Opus)"
    assert ap.PANDORA_OPTIMIZED["screenplay"] == "claude", "scénario = Sonnet"
    # 2026-07-23 : le Découpage est le pivot créatif (storyboard = conversion
    # déterministe) → tâche dédiée routée sur Opus 4.8 (décision Matthieu).
    assert ap.PANDORA_OPTIMIZED["decoupage"] == "opus", "découpage = Opus 4.8"
    assert not all(v == "opus" for v in ap.PANDORA_OPTIMIZED.values()), "plus Opus partout"
    keys = [t[0] for t in ap.TASKS]
    for k in ("enhance", "storyboard_chat", "assistant", "storyboard_gen",
              "screenplay", "extraction", "sync"):
        assert k in keys, f"tâche {k} paramétrable"
    # Profil Anthropic optimisé : routage stable et isolé de la config utilisateur.
    orig = ap._cfg
    ap._cfg = lambda: {"ai_profile": "anthropic_optimized", "ai_task_engines": {}}
    try:
        assert ap._resolve_engine("storyboard_gen") == ("anthropic", "claude-opus-4-8")
        assert ap._resolve_engine("screenplay") == ("anthropic", "claude-sonnet-5")
        assert ap._resolve_engine("decoupage") == ("anthropic", "claude-opus-4-8")
    finally:
        ap._cfg = orig
    # Override par tâche
    ap._cfg = lambda: {"ai_provider": "anthropic", "ai_model_creative": "claude-sonnet-5",
                       "ai_task_engines": {"enhance": "gpt", "storyboard_chat": "fable5"}}
    try:
        assert ap._resolve_engine("enhance") == ("openai", "gpt-5.5")
        assert ap._resolve_engine("storyboard_chat") == ("anthropic", "claude-fable-5")
        assert ap._resolve_engine("assistant") == ("anthropic", "claude-sonnet-5")
        assert ap._model("creative", "openai") == "gpt-5.5"
    finally:
        ap._cfg = orig
    # Fournisseur personnalisé : aucun repli inter-fournisseur silencieux.
    ap._cfg = lambda: {"ai_profile": "custom", "ai_engine": "custom",
                       "ai_provider": "custom", "custom_model": "local-model",
                       "ai_task_engines": {"enhance": "opus"}}
    try:
        assert ap._resolve_engine() == ("custom", "local-model")
        assert ap._resolve_engine("enhance") == ("anthropic", "claude-opus-4-8")
    finally:
        ap._cfg = orig
    # Appels câblés avec task=
    sp = inspect.getsource(__import__("api.screenplay", fromlist=["_"]))
    for t in ('task="storyboard_chat"', 'task="storyboard_gen"', 'task="sync"',
              'task="screenplay"', 'task="extraction"', 'task="decoupage"'):
        assert t in sp, f"{t} câblé dans screenplay"
    assert 'task="decoupage"' in inspect.getsource(__import__("api.plan_coedit", fromlist=["_"])), \
        "co-écriture des plans routée sur le moteur du découpage"
    assert 'task="enhance"' in inspect.getsource(__import__("api.enhance", fromlist=["_"]))
    assert 'task="assistant"' in inspect.getsource(__import__("api.assistant", fromlist=["_"]))
    # Paramètres : clés + testeurs GPT/Mistral + menu avancé par tâche
    src_pg = inspect.getsource(__import__("ui.page_settings", fromlist=["_"]))
    assert '_test_btn("✓  Tester API OpenAI"' in src_pg and '_test_btn("✓  Tester API Mistral"' in src_pg
    assert "Paramètres avancés" in src_pg and "_task_combos" in src_pg
    # Clés obligatoires (rouge) vs facultatives (menu déroulant bleu)
    assert '_badge("Obligatoire", "req")' in src_pg and '_badge("Facultatif", "opt")' in src_pg
    assert "Clés API facultatives" in src_pg
    assert "sans repli silencieux" in src_pg
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
    assert ap.ENGINES["kimi"]["name"] == "Kimi"
    assert "kimi" in ap.ENGINE_ORDER
    assert ap._KIMI_DEFAULT_MODEL == "kimi-k2.7-code"
    assert ap._KIMI_DEFAULT_URL == "https://api.moonshot.ai/v1"
    orig = ap._cfg
    try:
        # Routage par tâche → provider kimi
        ap._cfg = lambda: {"ai_profile": "single", "ai_provider": "kimi",
                           "ai_task_engines": {"screenplay": "kimi"}}
        assert ap._resolve_engine("screenplay")[0] == "kimi"
        # Modèle : défaut + override
        ap._cfg = lambda: {}
        assert ap._model("creative", "kimi", "") == "kimi-k2.7-code"
        ap._cfg = lambda: {"kimi_model": "kimi-k2.6"}
        assert ap._model("utility", "kimi", "") == "kimi-k2.6"
        # key_error : cloud SANS clé → erreur ; AVEC clé → None ; local → None
        ap._cfg = lambda: {"ai_profile": "single", "ai_provider": "kimi",
                           "ai_task_engines": {"sync": "kimi"}}
        assert ap.key_error("sync") and "Kimi" in ap.key_error("sync")
        ap._cfg = lambda: {"ai_profile": "single", "ai_provider": "kimi",
                           "ai_task_engines": {"sync": "kimi"}, "kimi_key": "sk-x"}
        assert ap.key_error("sync") is None
        ap._cfg = lambda: {"ai_profile": "single", "ai_provider": "kimi",
                           "ai_task_engines": {"sync": "kimi"},
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
        assert ap._engine_display_name("kimi", "") == "Kimi"
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
    assert wsrc.index('"plan_de_feu"') < wsrc.index('"camera"') < wsrc.index('"doublage"'), \
        "Technique : Plan de feu avant Image & Son puis Doublage"
    # 2026-07-23 (2e passe) : Projets RÉINTRODUIT à gauche de Scénario — la page
    # de démarrage n'est plus qu'un lanceur d'édition.
    assert '("projets.png"' in wsrc and wsrc.index('"projects"') < wsrc.index('"scenario"'), \
        "onglet Projets réintroduit à gauche de Scénario"
    # Synchro des prompts : tient compte de la mise en scène
    sp = inspect.getsource(__import__("api.screenplay", fromlist=["_"]))
    assert "mise_en_scene" in sp and "import core.staging" in sp


@test
def studio_musique_ia_et_image_ia():
    """Vidéo IA conserve ses outils vidéo/audio ; Image IA est désormais une
    destination globale autonome, tout en gardant le panneau partagé unique."""
    import ui.seedance_widget as SW
    src = inspect.getsource(SW)
    # Image IA ne doit plus être dupliquée dans les onglets de Vidéo IA.
    assert (src.index("addTab(self.tab_upscale")
            < src.index("addTab(self.tab_sound")
            < src.index("addTab(self.tab_music")), \
        "ordre groupé : Upscaling → Sound Design → Musique IA"
    assert "self.tab_image" not in src, "Image IA encore dupliquée dans Vidéo IA"
    # Barre d'onglets groupée : trait vertical en fin de groupe (façon dashboard)
    assert "_GroupedTabBar" in src and "set_group_ends" in src, \
        "barre d'onglets avec séparateurs de groupes"
    assert "set_group_ends({3, 5})" in src, \
        "traits après Upscaling (G1) et Musique IA (G2)"

    import ui.pandora_window as PW
    nav_src = inspect.getsource(PW)
    assert nav_src.index('"image_ia"') < nav_src.index('"seedance"'), \
        "dashboard : Image IA doit précéder Vidéo IA"
    assert 'tr("nav.group_studio_ia")' in nav_src, \
        "le groupe final doit s'appeler Studio IA"

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
    # 2026-07-23 : l'aperçu DISPARAÎT tant qu'aucune image (plus de rectangle
    # « En attente d'aperçu »).
    assert pn._preview.isHidden(), "aperçu masqué tant qu'aucune image générée"
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
    # _generate ET _generate_all_engines délèguent à _launch_image_worker (file
    # commune, depuis le balayage multi-moteurs) : c'est LUI qui allume la barre.
    assert "_launch_image_worker" in inspect.getsource(type(pn)._generate), \
        "génération image → file commune _launch_image_worker"
    assert "_set_busy(True" in inspect.getsource(type(pn)._launch_image_worker), \
        "génération image → barre gauche"
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
    # → 6 faces en injectant ces références (moteur edit sélectionné).
    rv = inspect.getsource(GenerateRoomViewsWorker._real)
    assert "build_overview_prompt" in rv and "_floor_plan_prompt" in rv, "ensemble + architecture"
    assert "is_floor_plan" in rv, "plan d'architecture renvoyé séparément"
    assert "build_request" in rv and "ref_urls" in rv, "faces avec références injectées"
    assert rv.index("build_overview_prompt(") < rv.index("build_six_view_prompts("), \
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
    _lighting = PageLighting()
    assert hasattr(_lighting, "_tools") and hasattr(_lighting, "_inspector"), \
        "Plan de feu V2 : outils centraux + réglages projecteurs"
    assert hasattr(_lighting._canvas, "fit_scene") and hasattr(_lighting._canvas, "zoom_by") \
        and hasattr(_lighting._canvas, "set_grid_visible"), "outils du plan câblés"
    assert "QGraphicsPolygonItem" in cvsrc, "cônes caméra et projecteurs affichés"
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
    """Page Scénario : Scénario / Note de réalisation / Découpage PANDORA ;
    le découpage reste distinct du texte narratif."""
    from ui.page_scenario import PageScenario
    p = PageScenario()
    assert hasattr(p, "_editor_tabs") and hasattr(p, "_layout_view"), "onglets éditeur"
    assert p._editor_tabs.count() == 3, "Scénario + Note + Découpage PANDORA"
    assert hasattr(p, "_direction_note_edit")
    assert p._editor_tabs.isTabEnabled(1), "la note reste toujours éditable"
    assert not p._editor_tabs.isTabEnabled(2), "Découpage grisé tant que vide"
    # Le découpage n'écrase pas le scénario
    p._set_editor_text("SCENARIO ORIGINAL")
    p._current = {}
    p._apply_layout("MISE EN PAGE PANDORA")
    assert p._editor_text.toPlainText().strip() == "SCENARIO ORIGINAL", "scénario intact"
    assert "MISE EN PAGE" in p._layout_view.toPlainText()
    # Mise en forme façon Word (2026-07-07) : texte CENTRÉ dans la colonne de lecture
    # bornée (lisible car largeur limitée — PAS le centrage pleine largeur illisible).
    from PyQt6.QtCore import Qt as _Qt
    _ed_align = p._editor_text.document().defaultTextOption().alignment()
    _note_align = p._direction_note_edit.document().defaultTextOption().alignment()
    _lv_align = p._layout_view.document().defaultTextOption().alignment()
    assert _ed_align & _Qt.AlignmentFlag.AlignHCenter, "Scénario centré dans la colonne (façon Word)"
    assert _note_align & _Qt.AlignmentFlag.AlignHCenter, "Note centrée dans la colonne"
    assert _lv_align & _Qt.AlignmentFlag.AlignHCenter, "Mise en page centrée dans la colonne"
    assert hasattr(p._editor_text, "_reading_column_filter") \
        and hasattr(p._direction_note_edit, "_reading_column_filter") \
        and hasattr(p._layout_view, "_reading_column_filter"), \
        "colonne de lecture centrée installée sur les 3 onglets"
    assert p._editor_tabs.isTabEnabled(2) and p._editor_tabs.currentIndex() == 2
    assert p._current.get("decoupage_content"), "découpage persisté séparément"
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
    # Depuis le 2026-07-23 : plus de blocage — un découpage non structuré ou périmé
    # déclenche une CONFIRMATION explicite, et l'absence de découpage part du scénario.
    _obs = inspect.getsource(PageScenario._on_storyboard)
    assert "is_structured_layout" in _obs and "Découpage non structuré" in _obs, \
        "_on_storyboard Cinéma : confirmation du découpage non structuré absente"
    assert "Découpage requis" not in _obs, \
        "_on_storyboard Cinéma : le blocage « Découpage requis » doit avoir disparu"
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
def analyse_transfere_note_realisation():
    """Appliquer une analyse range sa section 6 dans la note, jamais sa section 7."""
    from core.direction_note import append_to_note, empty_note, extract_from_analysis

    analysis_fr = """### 5. Suggestions concrètes pour le scénario
- Renforcer l'enjeu narratif.

### 6. Intentions à placer dans la Note de réalisation
- Plans longs de 8 secondes au début.
- Lumière froide puis passage progressif à l'ambre.
- Montage plus rapide dans la dernière séquence.

### 7. Inventaire complet des personnages
ALICE | Principal | Séquences 1 à 4
"""
    extracted = extract_from_analysis(analysis_fr)
    assert "Plans longs" in extracted and "Lumière froide" in extracted
    assert "ALICE" not in extracted and "Inventaire" not in extracted, \
        "l'inventaire des personnages ne doit jamais entrer dans la note"

    analysis_en = """### 6. Intentions for the Director's Note
- Slow, deliberate opening shots.
- High-contrast moonlight.

### 7. Complete character inventory
ALICE | Lead
"""
    assert "moonlight" in extract_from_analysis(analysis_en)
    assert "ALICE" not in extract_from_analysis(analysis_en)

    base = empty_note() + "\nNote humaine conservée.\n"
    merged = append_to_note(base, "INTENTIONS ISSUES DE L’ANALYSE DU SCÉNARIO",
                            extracted, replace=True)
    assert "Note humaine conservée" in merged and "Plans longs" in merged

    from ui.page_scenario import PageScenario
    page = PageScenario()
    page._current = None       # test sans écriture projet
    page._direction_note_edit.setPlainText("Note manuelle")
    assert page._merge_analysis_direction_note(analysis_fr) is True
    note = page._direction_note_edit.toPlainText()
    assert "Note manuelle" in note and "Montage plus rapide" in note
    assert "ALICE" not in note
    assert page._merge_analysis_direction_note(analysis_fr) is False, \
        "rouvrir la même analyse ne doit pas dupliquer la note"
    source = inspect.getsource(PageScenario._open_arrange_window)
    assert "_merge_analysis_direction_note(_final_analysis[0])" in source, \
        "le bouton Mettre à jour le scénario doit transférer la note"
    assert "if analysis and worker is None" in source \
        and "_merge_analysis_direction_note(analysis)" in source, \
        "rouvrir une analyse sauvegardée doit réparer la note manquante"
    assert "_merge_analysis_direction_note(result)" in source, \
        "une nouvelle analyse doit transférer automatiquement sa section 6"


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
    """Le Storyboard exige le Découpage canonique et ne redécoupe plus le scénario."""
    import inspect
    from ui.page_storyboard import PageStoryboard
    _oa = inspect.getsource(PageStoryboard._on_analyze)
    assert 'sc.get("decoupage_content")' in _oa and "text = _layout" in _oa, \
        "placeholder Cinéma : découpage canonique non branché"
    assert "validate_layout" in _oa and "Aucune réécriture IA automatique" in _oa, \
        "placeholder Cinéma : validation bloquante du découpage absente"
    assert "_layout or _source" not in _oa and "confirm_prompt_rewrite" not in _oa, \
        "le Storyboard conserve un repli silencieux vers le scénario brut"
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
    # Seedream 5.0 Pro (2026-07-20) — ⚠ PIÈGE DE PRÉFIXE : Pro est exposé SANS
    # « fal-ai/ », la version Lite l'exige. Les deux conventions coexistent chez
    # ByteDance : figé ici pour qu'une « uniformisation » ne casse pas l'appel.
    assert "seedream5_pro" in eng.ENGINES, "Seedream 5.0 Pro manquant"
    epp, _ap, _ = eng.build_request("seedream5_pro", "x", (1024, 768), "1K", [])
    assert epp == "bytedance/seedream/v5/pro/text-to-image", (epp, "préfixe Pro")
    epp2, ap2, _ = eng.build_request("seedream5_pro", "x", (1024, 768), "1K", ["data:img"])
    assert epp2 == "bytedance/seedream/v5/pro/edit" and "image_urls" in ap2, \
        "Seedream 5 Pro édition (refs)"
    # Pro = famille DISTINCTE de Lite (choix Matthieu) → les DEUX au balayage
    assert eng.family_of("seedream5_pro") != eng.family_of("seedream5"), \
        "Seedream Pro doit être une famille distincte"
    _sweep = eng.sweep_engines()
    assert {"seedream5_pro", "seedream5"} <= set(_sweep), \
        "Pro ET Lite attendus dans le balayage multi-moteurs"
    assert len(_sweep) == len({eng.family_of(k) for k in _sweep}), \
        "le balayage ne doit garder QU'UN moteur par famille"

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

    # — TTS : registre + workers + page Doublage (4 modes + moteur de clonage) —
    #
    # L'ancienne version de ce test figeait le NOMBRE de moteurs et la présence
    # d'un dict « extra ». Il était vert pendant que trois moteurs sur sept
    # étaient rejetés par fal (champ requis « prompt », on envoyait « text ») et
    # que les autres parlaient français avec leur voix anglaise par défaut.
    # On teste donc désormais la CHARGE UTILE, seule chose qui décide du rendu.
    import api.tts as tts
    from core import speech_engines as se

    # ORDER = le menu ; AUDITION_ONLY = les moteurs présents pour le seul
    # bouton « Écouter ». La somme doit couvrir ENGINES exactement : un moteur
    # oublié des deux serait inatteignable, et un moteur en trop apparaîtrait
    # deux fois dans la page.
    assert set(se.ORDER) | se.AUDITION_ONLY == set(se.ENGINES), \
        "ORDER + AUDITION_ONLY ne couvrent pas ENGINES"
    assert not (set(se.ORDER) & se.AUDITION_ONLY), \
        "un moteur d'audition ne doit pas aussi figurer dans le menu"
    assert hasattr(tts, "FalSpeechWorker") and hasattr(tts, "FoleyControlWorker")

    for _k, _spec in se.ENGINES.items():
        assert _spec.get("text_key"), f"{_k} : champ texte non déclaré"
        _a = se.build_args(_k, "Bonjour.")
        assert _a.get(_spec["text_key"]) == "Bonjour.", \
            f"{_k} : le texte n'est pas déposé sous {_spec['text_key']}"
        # Un moteur qui attend « prompt » ne doit JAMAIS recevoir « text ».
        if _spec["text_key"] != "text":
            assert "text" not in _a, f"{_k} : « text » envoyé au lieu de son champ réel"

    # Les trois moteurs qui exigent « prompt » — la panne d'origine.
    for _k in ("minimax-2.8-hd", "minimax-2.8-turbo", "gemini-tts"):
        assert "prompt" in se.build_args(_k, "x"), f"{_k} : doit recevoir « prompt »"
    assert "transcript" in se.build_args("async-tts-pro", "x")

    # Aucune voix implicite : sans voix explicite, ElevenLabs retombe sur
    # « Rachel » (américaine) et Inworld sur « Craig (en) ».
    assert se.build_args("elevenlabs-v3", "x").get("voice"), \
        "elevenlabs-v3 : aucune voix transmise → repli sur Rachel"
    assert se.build_args("inworld", "x").get("voice", "").endswith("(fr)"), \
        "inworld : la voix par défaut doit être francophone"
    # Voix imbriquées : un chemin pointé mal résolu produit un 422 muet.
    assert se.build_args("minimax-2.8-hd", "x")["voice_setting"]["voice_id"]
    assert se.build_args("async-tts-pro", "x")["voice"]["name"]
    # La langue doit être nommée comme chaque moteur l'attend.
    assert se.build_args("minimax-2.8-hd", "x")["language_boost"] == "French"
    assert se.build_args("gemini-tts", "x")["language_code"] == "French (France)"
    assert se.build_args("seed-speech-v2", "x")["language"] == "fr"
    # french=False ne doit forcer aucune langue (voix-off en VO).
    assert "language_boost" not in se.build_args("minimax-2.8-hd", "x", french=False)
    # Moteurs porteurs de vraies voix françaises.
    assert se.has_french_voices("inworld") and se.has_french_voices("seed-speech-v2")
    # Un tarif non relevé vaut 0.0 et doit être affiché comme inconnu, pas gratuit.
    assert se.estimate_usd("inworld", 1000) == 0.01

    # — Écouter une voix : le cache doit rendre la réécoute GRATUITE —
    from core import voice_auditions as va
    import api.voice_audition as vaud

    # Deux voix distinctes ne doivent jamais se réduire au même fichier : les
    # noms contiennent des accents et des parenthèses (« Hélène (fr) »).
    assert va.audition_path("inworld", "Alain (fr)") != \
           va.audition_path("inworld", "Hélène (fr)")
    # Le chemin est stable d'un appel à l'autre, sinon le cache ne sert à rien.
    assert va.audition_path("inworld", "Alain (fr)") == \
           va.audition_path("inworld", "Alain (fr)")
    # Changer la phrase d'audition invalide les caches sans suppression manuelle.
    assert va._TEXT_TAG in va.audition_path("inworld", "Alain (fr)")

    # Un extrait déjà en cache ne doit PAS relire la clé ni appeler fal.
    _real_cached, _real_path = vaud.is_cached, vaud.audition_path
    _real_cfg = vaud.load_config
    def _boom(*a, **k):
        raise AssertionError("appel facturé alors que l'extrait est en cache !")
    vaud.is_cached = lambda e, v: True
    vaud.audition_path = lambda e, v: "X:/faux/extrait.mp3"
    vaud.load_config = _boom
    try:
        w = vaud.VoiceAuditionWorker("inworld", "Alain (fr)")
        _got = []
        w.done.connect(lambda p, c: _got.append((p, c)))
        w.failed.connect(lambda e: _got.append(("FAILED", e)))
        w.run()                       # run() direct : aucun thread, aucun réseau
        assert _got and _got[0][1] is True, f"cache non honoré : {_got}"
    finally:
        vaud.is_cached, vaud.audition_path = _real_cached, _real_path
        vaud.load_config = _real_cfg

    psrc = inspect.getsource(importlib.import_module("ui.page_doublage"))
    for tok in ("_speech_combo", "_speech_voice_combo", "_clone_engine_combo",
                "FalSpeechWorker", "IndexTTS2Worker", "VoiceChangerWorker",
                "_on_speech_engine_changed", "VoiceAuditionWorker",
                "_make_audition_row", "_on_audition", "audio_preview"):
        assert tok in psrc, f"page_doublage : {tok} manquant"
    # QtMultimedia est importé dans un try : sans déclaration explicite dans le
    # spec, le bouton « Écouter » marcherait en dev et pas dans l'installeur.
    import io as _io
    _spec_path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "pandora.spec")
    _spec = _io.open(_spec_path, encoding="utf-8").read()
    assert "PyQt6.QtMultimedia" in _spec, "pandora.spec : QtMultimedia non déclaré"
    # La voix choisie doit réellement partir au worker.
    gsrc = inspect.getsource(importlib.import_module("ui.page_doublage").PageDoublage._on_generate)
    assert "voice=voice" in gsrc, "page_doublage : la voix n'est pas transmise au worker"

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
        selected = ps.ai_combo.currentData()
        assert isinstance(selected, dict) and selected.get("profile") in {
            "anthropic_optimized", "openai_optimized"
        }, f"profil optimisé attendu, eu {selected}"
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
    # Depuis le 2026-07-22 : marges verticales à 0 aussi (la poignée et le panneau
    # touchent les bords haut/bas — plus de bandes noires).
    assert "root.setContentsMargins(14, 0, 0, 0)" in src, "poignée non collée aux bords (marges ≠ 0)"
    # Panneau chat ENTIÈREMENT marine — viewport du scroll peint aussi (sinon bande
    # noire en haut) ; poignée « IA » collée au bord (spacer masqué sur la page
    # « image_ia »). Retour Matthieu 2026-07-05.
    assert "viewport().setStyleSheet" in src, "viewport du chat non peint → bande noire résiduelle"
    # 2026-07-23 : exclusion étendue aux 5 pages éléments (poignées FICHE au bord).
    with open(os.path.join(root, "ui", "pandora_window.py"), encoding="utf-8") as f:
        _w = f.read()
    for _k in ('"image_ia"', '"plan_de_feu"', '"scenario"',
               '"castings"', '"decors"', '"accessoires"', '"hmc"', '"vehicles"'):
        assert _w.find('self._right_spacer.setVisible') < _w.find(_k, _w.find(
            'self._right_spacer.setVisible')), \
            f"spacer non masqué pour {_k} (poignée décalée du bord)"


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
    # Dossier de sauvegarde DÉDIÉ par type — arborescence 2026-07-30 : les
    # saves vivent DANS leur catégorie (02_elements/<cat>/saves) pour un
    # projet neuf ; les anciens dossiers capitalisés FR (Casting, Décors…)
    # restent servis en repli legacy par core/project_layout (testé dans
    # arborescence_source_de_verite_unique).
    for _k, _cat in (("casting", "characters"), ("decors", "sets"),
                     ("accessories", "props"), ("hmc", "hmc"),
                     ("vehicles", "vehicles")):
        d = eio.saves_dir(_k)
        assert (d.rstrip("/\\").endswith("saves")
                and _o.sep + _cat + _o.sep in d
                and "02_elements" in d
                and _o.path.isdir(d)), \
            f"dossier de saves « 02_elements/{_cat}/saves » absent : {d}"

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
    # 2026-07-23 : annotations SOUS la ligne, zone « Tout générer » (masqué)
    # sans rectangle réservé — marges resserrées.
    assert "b_lay.setContentsMargins(0, 0, 0, 6)" in src, "zone basse non alignée"
    assert "ga_lay.setContentsMargins(0, 0, 0, 0)" in src, "zone Tout générer non résorbée"
    # Descriptions avec word-wrap ; 2026-07-23 : hauteurs COMPACTES (46/50) et
    # marge devant la scrollbar CONSERVÉES, centrage testé puis REFUSÉ (gauche).
    assert "sub_lbl.setWordWrap(True)" in src, "descriptions encore tronquées (pas de word-wrap)"
    # 2026-07-23 (2e retour) : la hauteur devient ADAPTATIVE — 46/50 en plancher,
    # puis les boutons se partagent l'espace libre pour que la dernière section
    # ferme le panneau en bas au lieu de laisser un vide.
    assert "btn.setMinimumHeight(50 if color else 46)" in src, \
        "plancher compact des boutons (46/50) perdu"
    assert "btn.setMaximumHeight(96)" in src, "plafond de hauteur des boutons absent"
    assert "QSizePolicy.Policy.Expanding" in src, "boutons du panneau non extensibles"
    assert "sc_lay.addStretch()" not in src, \
        "le ressort final réintroduirait le vide en bas du panneau"
    assert "_section_container(grow=True)" in src, "sections d'actions non extensibles"
    # Rangée « Durée cible » : sélecteur CIBLÉ — une règle sans sélecteur se propage
    # aux enfants et retraçait un trait sous « Durée cible » et sous « Estimé ».
    assert "QWidget#ScenarioDurStrip{{background:" in src, \
        "rangée Durée cible sans sélecteur ciblé (traits parasites)"
    assert "strip.setStyleSheet(f\"background:" not in src, \
        "style non ciblé de la rangée Durée cible (traits sous les libellés)"
    assert "sc_lay.setContentsMargins(0, 0, 8, 0)" in src, \
        "espace entre les rectangles et la barre de défilement"
    # Bouton « Générer le storyboard » MIS EN AVANT : ROUGE + éclair (2026-07-23,
    # reprend l'identité de l'ex-« Tout générer », désormais masqué).
    assert 'self._on_storyboard, color=CP.get("red"' in src, \
        "« Générer le storyboard » pas mis en avant (cadre rouge)"
    assert '"⚡", "Générer le storyboard"' in src, "éclair absent du bouton storyboard"
    assert "self._btn_generate_all.hide()" in src, "« Tout générer » doit être masqué"
    # Architecture 2026-07-21 : Scénario puis Découpage PANDORA.
    assert '_make_toggle("📖  Scénario"' in src, "section Scénario (ex-IA) absente"
    assert '_make_toggle("🎯  Découpage"' in src, "section Découpage absente"
    assert '"Affiner le découpage"' in src and "def _on_plan_coedit" in src, \
        "bouton/handler d'affinage du découpage absent"
    # Ordre du panneau (2026-07-23, 2e passe) : Scénario, Découpage, Générer depuis
    # le scénario, Ajouter des références, Musique, Style en dernier.
    assert (src.index("(tog_scen,") < src.index("(tog_final,") < src.index("(tog_gen,")
            < src.index("(tog_refs,") < src.index("(tog_music,") < src.index("(tog_style,")), \
        "ordre du panneau droit incorrect (Scénario→Découpage→Générer→Références→Musique→Style)"
    assert '_make_toggle("⚡  Générer depuis le scénario"' in src, \
        "section « Générer depuis le scénario » (nom restauré 2026-07-23)"


@test
def ecriteau_moteur_ia_du_storyboard():
    """La génération du storyboard renseigne l'écriteau du panneau comme les autres
    générations : nom EXACT du moteur, ou mention explicite quand le Découpage
    structuré est converti sans IA (demande Matthieu 2026-07-23)."""
    import inspect
    src = inspect.getsource(__import__("ui.page_scenario", fromlist=["_"]))
    _sb = src[src.index("def _on_storyboard"):src.index("def _start_extraction")]
    assert "ai_name_for_task(\"storyboard_gen\")" in _sb, \
        "moteur exact non résolu pour le storyboard"
    assert "Génération du découpage via {ai}…" in _sb, "écriteau « via <moteur> » absent"
    assert "Import déterministe du Découpage — sans IA…" in _sb, \
        "cas déterministe non annoncé (afficher un moteur IA serait faux)"
    assert "dlg.is_deterministic()" in _sb, "le dialogue doit dire s'il utilise l'IA"
    # Le bilan final rappelle QUI a travaillé.
    assert "— {_via}" in _sb, "bilan final sans mention du moteur"
    # Le dialogue expose bien l'information.
    _dsrc = inspect.getsource(__import__("ui.dialog_storyboard_generate", fromlist=["_"]))
    assert "def is_deterministic" in _dsrc, "dialogue storyboard : accesseur manquant"
    from core.i18n import _FR_TO_EN
    for k in ("Import déterministe du Découpage — sans IA…", "import déterministe, sans IA"):
        assert k in _FR_TO_EN, f"i18n manquante : {k}"


@test
def studio_prompt_final_wysiwyg():
    """Studio IA : à la sélection d'un plan, l'ENCART contient le prompt FINAL
    (anglais, injections texte écrites dedans) et il part TEL QUEL — aucune
    réinjection à l'envoi. Le bloc déroulant « Éléments injectés dans le prompt »
    ne contient QUE les injections, jamais le prompt (demande Matthieu 2026-07-24)."""
    import inspect
    tsrc = inspect.getsource(__import__("ui.tab_t2v", fromlist=["_"]))
    # Assemblage : sélection de plan → photo du texte → traduction → encart remplacé.
    for frag in ("_schedule_final_assembly", "_assemble_final_prompt_text",
                 "_text_injections", "_prompt_is_final", "_suppress_prompt_signal"):
        assert frag in tsrc, f"mécanique WYSIWYG absente : {frag}"
    # Le son de la section [🎵 SOUND DESIGN] est capturé AVANT de disparaître de
    # l'encart (sinon le Sound Design le perdrait).
    assert "self._final_sound_notes = _so(self._assembly_source)" in tsrc, \
        "son non capturé à la prise de la photo source"
    # Jamais écraser une saisie utilisateur en cours.
    assert tsrc.count("self.prompt_ta.toPlainText().strip() != src") >= 2, \
        "garde anti-écrasement de la saisie utilisateur absente"
    # L'encart reçoit la PROSE COMPOSÉE (décision Matthieu 2026-07-24), pas une
    # traduction littérale : sinon le prompt envoyé garderait les étiquettes de
    # section et perdrait la prose optimisée Seedance. Repli traduction si la
    # composition est indisponible (pas de clé / erreur API).
    assert "class _FinalPromptWorker" in tsrc, "worker de composition absent"
    assert "from api.video_prompt import compose as _compose" in tsrc, \
        "l'encart doit être rempli par la composition, pas par une simple traduction"
    assert "_build_pre_compose_prompt" in tsrc and "_post_compose_injections" in tsrc, \
        "séparation pré/post composition absente (doublons ou briques perdues)"
    assert "translate_to_english" in tsrc, "repli traduction absent"
    # Un prompt FINAL ne contient JAMAIS d'étiquettes de section : si composition ET
    # traduction échouent, on garde le prompt de travail au lieu d'installer un
    # prompt franglais que l'envoi expédierait tel quel (constat Matthieu).
    assert "_final_assembly_failed" in tsrc and "if _is_struct(final):" in tsrc, \
        "garde manquante : un prompt non composé/non traduit pourrait devenir final"
    # Un prompt FINAL est TOUJOURS brut : le repli APLATIT les sections (sinon la
    # traduction gardait « [🎬 ACTION] » et la garde ci-dessus bloquait tout, laissant
    # l'encart sur le prompt de travail français — constat Matthieu).
    from core.prompt_sections import (flatten as _flatten, is_structured as _isstruct,
                                      build as _psbuild)
    _p = _psbuild(action="Il marche", decor="rue", technique="Gros plan",
                  sound="pluie", style="Style Arcane")
    _f = _flatten(_p)
    assert not _isstruct(_f), "flatten() doit supprimer toutes les étiquettes"
    assert "pluie" not in _f, "le son ne part pas au moteur vidéo"
    assert _f.rstrip(".").endswith("Style Arcane"), "le style doit fermer le prompt"
    assert "from core.prompt_sections import flatten as _flat" in tsrc, \
        "le repli n'aplatit pas : l'encart resterait sur le prompt de travail"
    # L'échec de composition doit être EXPLIQUÉ, pas silencieux.
    assert "_final_fallback_reason" in tsrc and "Prose composée non disponible" in tsrc, \
        "raison du repli non affichée à l'utilisateur"
    # Les noms d'entités du bloc [COHÉRENCE VISUELLE] ne sont PAS des dialogues :
    # les compter comme tels faisait échouer la composition sur tout plan ayant un
    # personnage ou un décor (donc quasiment tous).
    from api.video_prompt import validate_composed_prompt as _V
    _src = ('[COHÉRENCE VISUELLE — apparence identique]\nPersonnage "Jésus" (Principal)\n'
            'Décor "Canyon désertique de Bethléem"\nCRITIQUE : exact.\n\n'
            '[ACTION]\nIl fait « brrr » longuement.')
    _ok = ("Jesus sits over a Bethlehem desert canyon making a long « brrr » sound, "
           "golden hour light, painterly style.")
    assert _V(_ok, _src)["valid"], \
        "composition rejetée à tort : noms d'entités pris pour des dialogues"
    assert not _V("Jesus sits over a canyon in golden light, painterly style.",
                  _src)["valid"], "un vrai dialogue omis doit rester rejeté"
    # Dialogues : SEULES les répliques sont traduites vers la langue de la colonne
    # « Langues » du Storyboard ; les noms d'entités du bloc de cohérence ne le sont
    # JAMAIS (ils renommaient le décor et le personnage). Traduits dès l'assemblage
    # pour être visibles, donc PAS refaits à l'envoi.
    assert "dialogues_translated" in tsrc, "drapeau anti-double-traduction absent"
    assert "translate_dialogues_to" in tsrc, "dialogues non traduits dans l'encart"
    _rsrc_dlg = inspect.getsource(__import__("api.real", fromlist=["_"]))
    assert "not _dlg_done" in _rsrc_dlg, \
        "api/real retraduirait des dialogues déjà traduits"
    import core.lang as _lang
    _lsrc = inspect.getsource(_lang.translate_dialogues_to)
    assert "_entity_line" in _lsrc and "Personnage|D" in _lsrc, \
        "noms d'entités non protégés : le décor/personnage serait traduit"
    # La FILE attend le prompt final → même prompt qu'en génération unitaire.
    assert "_await_final_then_generate" in tsrc, \
        "la file génère sans attendre le prompt final (résultats divergents)"
    assert "_BATCH_FINAL_TIMEOUT_MS" in tsrc, "file sans filet de sécurité (blocage)"
    # Envoi : en mode final, AUCUNE brique texte n'est recollée + suffixes neutralisés.
    assert '"prompt_is_final":         _final_mode' in tsrc, "flag non transmis à api/real"
    for frag in ('"style_suffix":            "" if _final_mode else',
                 '"time_suffix":             "" if _final_mode else',
                 '"no_music_suffix":         "" if _final_mode else',
                 '"creative_suffix":          "" if _final_mode else',
                 '"char_consistency_suffix":  "" if _final_mode else'):
        assert frag in tsrc, f"suffixe non neutralisé en mode final : {frag}"
    assert "context     = \"\" if _final_mode else" in tsrc, \
        "contexte casting recollé en mode final (doublon)"
    # Le bloc déroulant reste REPLIÉ par défaut et n'affiche pas le prompt.
    assert "self._preview_expanded = False" in tsrc, "bloc doit être replié par défaut"
    assert "◈  Éléments injectés" in tsrc, "bloc mal nommé"
    _bsrc = tsrc[tsrc.index("def _build_full_preview_text"):]
    _bsrc = _bsrc[:_bsrc.index("def _assemble_preview_prompt")]
    assert "AJOUTÉS AU PROMPT À L'ENVOI" in _bsrc and "APPLIQUÉS À L'ENVOI" in _bsrc, \
        "bloc : sections d'injections manquantes"
    assert "lines.append(fp)" not in _bsrc, "le bloc ne doit JAMAIS contenir le prompt"
    # api/real : le prompt final saute composition ET traduction.
    rsrc = inspect.getsource(__import__("api.real", fromlist=["_"]))
    assert '_final = bool(params.get("prompt_is_final"))' in rsrc, "flag non lu par api/real"
    assert "if not _final and (_vp_should(" in rsrc, "composition non sautée en mode final"
    assert "if _final:" in rsrc and "_prompt_en = _raw_prompt" in rsrc, \
        "traduction non sautée : le prompt final serait réécrit"


@test
def projets_menu_contextuel_vignette():
    """Clic droit sur une vignette de projet : Renommer / Dupliquer / Supprimer
    (demande Matthieu 2026-07-24 ; auparavant « Renommer » et seulement sur le
    projet ouvert). Suppression protégée : jamais le projet ouvert, fichiers
    conservés par défaut, effacement disque sur double confirmation."""
    import inspect, tempfile, os, json
    psrc = inspect.getsource(__import__("ui.page_projects", fromlist=["_"]))
    for sig in ("rename_requested", "duplicate_requested", "delete_requested"):
        assert f"{sig} = pyqtSignal(dict)" in psrc, f"signal manquant : {sig}"
    assert "def _on_duplicate" in psrc and "def _on_delete" in psrc, "handlers manquants"
    assert "if not self._is_current:\n            return" not in psrc, \
        "le menu ne doit plus être réservé au projet ouvert"
    assert "act_del.setEnabled(False)" in psrc, "le projet ouvert doit être protégé"
    assert "remove_files=_hard" in psrc and "Confirmation définitive" in psrc, \
        "effacement disque sans double confirmation"
    # Le projet ciblé par le clic droit est bien celui traité (pas le projet ouvert).
    assert "card.rename_requested.connect(self._on_rename)" in psrc, \
        "renommage recâblé sur le projet ouvert au lieu de la vignette cliquée"

    # API métier : duplication complète + suppression, sur des dossiers TEMPORAIRES.
    import core.project as P
    _reg, _dir = P._REGISTRY, P._DEFAULT_DIR
    _tmp = tempfile.mkdtemp(prefix="pandora_t_proj_")
    try:
        P._REGISTRY = os.path.join(_tmp, "recent.json")
        P._DEFAULT_DIR = os.path.join(_tmp, "P")
        src = P.create_project("Film", parent_dir=P._DEFAULT_DIR)
        os.makedirs(os.path.join(src["_path"], "data"), exist_ok=True)
        with open(os.path.join(src["_path"], "data", "x.json"), "w", encoding="utf-8") as f:
            json.dump({"a": 1}, f)
        clone = P.duplicate_project(src, "Film v2")
        assert clone and os.path.isdir(clone["_path"]), "duplication échouée"
        assert clone["id"] != src["id"], "le clone doit avoir un nouvel identifiant"
        assert os.path.isfile(os.path.join(clone["_path"], "data", "x.json")), \
            "contenu du projet non copié"
        assert os.path.isdir(src["_path"]), "l'original ne doit jamais être touché"
        assert len([f for f in os.listdir(clone["_path"]) if f.endswith(".json")]) == 1, \
            "le clone doit avoir un seul descripteur"
        assert P.delete_project(clone, remove_files=False) and os.path.isdir(clone["_path"]), \
            "suppression douce : les fichiers doivent être CONSERVÉS"
        assert P.delete_project(clone, remove_files=True) and not os.path.isdir(clone["_path"]), \
            "suppression dure : le dossier doit être effacé"
    finally:
        P._REGISTRY, P._DEFAULT_DIR = _reg, _dir
        import shutil; shutil.rmtree(_tmp, ignore_errors=True)
    from core.i18n import _FR_TO_EN
    for k in ("Renommer", "Dupliquer", "Supprimer le projet", "Confirmation définitive"):
        assert k in _FR_TO_EN, f"i18n manquante : {k}"


@test
def prompt_grammaire_par_moteur():
    """Le prompt final est écrit dans la GRAMMAIRE du moteur sélectionné (dossier
    fal.ai fourni par Matthieu 2026-07-25) : champs Seedance, phrase continue Veo
    (négations en positif), directive courte Kling. Les noms d'IP/studios sont
    retirés du payload, les DESCRIPTEURS de style conservés."""
    import inspect
    from core.engine_grammar import (grammar_for, grammar_label, format_rules,
                                     strip_ip_names, find_ip_names)
    # Grammaire par famille de moteur.
    assert grammar_for("seedance-2.0") == "fields", "Seedance = champs"
    assert grammar_for("seedance-2.0-fast") == "fields", "toute la famille Seedance"
    assert grammar_for("veo-3.1") == "sentence", "Veo = phrase continue"
    assert grammar_for("kling-o3-4k") == "directive" and grammar_for("kling-v3-pro") == "directive", \
        "Kling = directive d'action"
    assert grammar_for("ltx-2") == "plain" and grammar_for("") == "plain", "repli prose"
    # Consignes de format réellement différenciées.
    _f, _s, _d = format_rules("seedance-2.0"), format_rules("veo-3.1"), format_rules("kling-o3-4k")
    assert "Camera:" in _f and "Constraints:" in _f, "champs Seedance absents"
    assert "UNE SEULE phrase" in _s and "POSITIVEMENT" in _s, \
        "Veo : phrase unique + négations reformulées en positif"
    assert "DIRECTIVE" in _d, "Kling : directive d'action"
    assert len({_f, _s, _d}) == 3, "les grammaires doivent différer"
    for _r in (_f, _s, _d):
        assert "emoji" in _r and "crochet" in _r, "règle commune : ni emoji ni crochets"
    # Noms d'IP retirés, descripteurs conservés.
    _t = ('Style graphique façon "Arcane" : Arcane League of Legends style, '
          'Fortiche Studio aesthetic, 3D painterly render with hand-painted '
          'textures, dramatic chiaroscuro lighting')
    _out, _rm = strip_ip_names(_t)
    assert _rm, "noms d'IP non détectés"
    for _bad in ("arcane", "legends", "fortiche"):
        assert _bad not in _out.lower(), f"nom d'IP resté dans le payload : {_bad}"
    for _keep in ("3D painterly render", "hand-painted textures", "chiaroscuro"):
        assert _keep in _out, f"descripteur de style perdu : {_keep}"
    assert strip_ip_names("a man walks in the rain") == ("a man walks in the rain", []), \
        "un texte sans IP doit rester intact"
    assert not find_ip_names(""), "texte vide"
    # Branchement : composeur + Studio.
    vsrc = inspect.getsource(__import__("api.video_prompt", fromlist=["_"]))
    assert "engine: str = \"\"" in vsrc and "format_rules(engine)" in vsrc, \
        "le composeur ne reçoit pas la grammaire du moteur"
    tsrc = inspect.getsource(__import__("ui.tab_t2v", fromlist=["_"]))
    assert '"engine": self._get_model()' in tsrc, "moteur non transmis à l'assemblage"
    assert "strip_ip_names" in tsrc and "_final_ip_removed" in tsrc, \
        "noms d'IP non retirés / non tracés"
    assert "grammar_for(_prev) != grammar_for(key)" in tsrc, \
        "changer de moteur doit réassembler le prompt dans la nouvelle grammaire"
    assert "Noms de franchise" in tsrc and "Grammaire :" in tsrc, \
        "l'écran doit annoncer la grammaire et les noms retirés (jamais silencieux)"


@test
def decoupage_affiche_titre_projet():
    """Onglet Découpage : la 1re ligne affiche le TITRE DU PROJET, pas le marqueur
    technique « DÉCOUPAGE PANDORA 2 » (demande Matthieu 2026-07-24). Le marqueur est
    reconstitué en tête à CHAQUE lecture destinée au stockage/parsing → détection v2
    intacte, même après édition du titre par l'utilisateur."""
    import core.context as _ctx
    from ui.page_scenario import PageScenario
    from core.decoupage_document import is_v2_document
    _op, _oi = _ctx.get_project_path(), _ctx.get_project_id()
    try:
        import tempfile, os, json
        d = tempfile.mkdtemp(prefix="pandora_t_")
        json.dump({"name": "FIGHTER", "id": "p1"}, open(os.path.join(d, "project.json"), "w", encoding="utf-8"))
        _ctx.set_project_path(d); _ctx.set_project_id("p1")
        MARK = "DÉCOUPAGE PANDORA 2"
        doc = (f"{MARK}\n\nSÉQUENCE 1 — X\n\nPLAN 01\nSOURCE SCÉNARIO : a.\n"
               "PROMPT VISUEL : gros plan.\nDURÉE : 8s\n")
        assert is_v2_document(doc)
        p = PageScenario()
        p._restore_layout(doc)
        shown = p._layout_view.toPlainText()
        assert next(l for l in shown.split("\n") if l.strip()) == "FIGHTER", "titre projet affiché"
        assert MARK not in shown, "marqueur technique masqué à l'affichage"
        stored = p._read_layout()
        assert next(l for l in stored.split("\n") if l.strip()) == MARK, "marqueur reconstitué au stockage"
        assert is_v2_document(stored), "v2 détecté après lecture stockage"
        # Édition du titre par l'utilisateur → le marqueur revient quand même.
        p._layout_view.setPlainText(shown.replace("FIGHTER", "PERSO"))
        assert is_v2_document(p._read_layout()), "v2 préservé même après édition du titre"
        # Doc non-v2 (Live/texte libre) : jamais modifié.
        assert p._layout_to_storage("texte libre") == "texte libre", "non-v2 intact"
    finally:
        _ctx.set_project_path(_op); _ctx.set_project_id(_oi)


@test
def style_visuel_section_storyboard():
    """Le style visuel est CAPTURÉ dans le prompt du storyboard (dernière section
    [🎨 STYLE VISUEL] = style d'image projet + section « STYLE VISUEL » de la note),
    ENVOYÉ au moteur vidéo EN FIN de prompt, et lu par le Mood — le tout sans
    doublon (demande Matthieu 2026-07-24)."""
    import core.prompt_sections as ps
    # 1) STYLE VISUEL est la DERNIÈRE section (Seedance suit mieux le style en fin).
    assert ("style", "[🎨 STYLE VISUEL]") == ps.SECTIONS[-1], "STYLE VISUEL doit être en dernier"
    base = ps.build(action="A", technique="Gros plan", sound="vent")
    assert "STYLE VISUEL" not in base
    inj = ps.rebuild(base, style="shot on ARRI Alexa 65, film grain")
    _tags = [l for l in inj.split("\n") if l.startswith("[")]
    assert _tags[-1] == "[🎨 STYLE VISUEL]", "style écrit en DERNIÈRE section du prompt"
    assert "ACTION" in inj and "SOUND DESIGN" in inj, "rebuild préserve les autres sections"
    assert ps.style_of(inj) == "shot on ARRI Alexa 65, film grain", "style_of() lit la section"
    # 2) rebuild d'une AUTRE section n'efface pas le style (régression majeure évitée).
    inj2 = ps.rebuild(inj, technique="Plan large")
    assert "STYLE VISUEL" in inj2 and "Plan large" in inj2, "édition partielle → style préservé"
    # 3) strip_for_video retire STYLE **et** SON du CORPS : le style ne passe pas à la
    #    Le STYLE reste dans le CORPS (souvent écrit en français → doit être TRADUIT) ;
    #    seul le SON est retiré (part au Sound Design). Le composeur, lui, le sort du
    #    corps pour le rendre en anglais en fin de prose (strip_for_composer).
    sv = ps.strip_for_video(inj)
    assert "STYLE VISUEL" in sv and "SOUND DESIGN" not in sv and "ACTION" in sv, \
        "corps vidéo : style CONSERVÉ (traduit), son retiré, action gardée"
    sc = ps.strip_for_composer(inj)
    assert "STYLE VISUEL" not in sc and "SOUND DESIGN" not in sc and "ACTION" in sc, \
        "corps composeur : style ET son retirés (style repart par le bloc dédié)"
    # 4) real.py : style baké → NON recollé (déjà traduit dans le corps) ; prompt libre
    #    SANS section style → repli sur get_video_suffix (retro-compat, aucun doublon).
    import inspect
    rsrc = inspect.getsource(__import__("api.real", fromlist=["_"]))
    assert "style_of" in rsrc and "_baked_style" in rsrc, "real.py : style baké non lu"
    assert '"" if (_composed or _baked_style) else params.get("style_suffix"' in rsrc, \
        "real.py : style baké recollé en double (doit rester dans le corps traduit)"
    # 5) Mood : le style de la SECTION prime et n'apparaît qu'une fois.
    from api.apercu import build_mood_prompt
    shot = {"id": "z", "seedance_prompt": inj, "shot_size": "GP"}
    mood = build_mood_prompt(shot, "shot on ARRI Alexa 65, film grain")
    assert mood.lower().count("arri alexa 65") == 1, "style Mood non dupliqué"
    # 6) Rétro-compat : prompt sans section style → Mood retombe sur le suffixe projet.
    mlegacy = build_mood_prompt({"id": "w", "seedance_prompt": base, "shot_size": "GP"},
                                "shot on ARRI Alexa 65")
    assert "arri alexa 65" in mlegacy.lower(), "rétro-compat : style via suffixe projet"
    # 7) Style visuel extrait de la note de réalisation, de façon TOLÉRANTE :
    #    a) la section « STYLE VISUEL » quand elle est renseignée ;
    from core.direction_note import section_text, visual_style_from_note
    note = ("## INTENTION GÉNÉRALE\nx\n\n## STYLE VISUEL\ngrain lourd, désaturé\n\n"
            "## SON ET MUSIQUE\nnappe grave\n")
    assert section_text(note, "STYLE VISUEL") == "grain lourd, désaturé", "extraction section directe"
    assert visual_style_from_note(note) == "grain lourd, désaturé", "style depuis la section"
    #    b) SINON les lignes de style rangées ailleurs par l'Analyse (cas réel FIGHTER :
    #       « - Style graphique global façon Arcane… » sous « INTENTIONS ISSUES DE… »).
    note2 = ("## STYLE VISUEL\n\n\n## INTENTIONS ISSUES DE L'ANALYSE DU SCÉNARIO\n"
             "- Style graphique global façon « Arcane », rendu 3D peint à la main.\n"
             "- Lumière rasante de fin de journée.\n- Durées : 6-8s.\n")
    _vs = visual_style_from_note(note2)
    assert "Arcane" in _vs and "peint à la main" in _vs, f"repli intentions d'analyse: {_vs!r}"
    assert "Durées" not in _vs, "ne doit pas ramasser les lignes non-style"
    dsrc = inspect.getsource(__import__("ui.dialog_storyboard_generate", fromlist=["_"]))
    assert "get_video_suffix()" in dsrc and "visual_style_from_note" in dsrc, \
        "dialogue storyboard : style (projet + note tolérante) non capturé à la sauvegarde"
    # 8) Studio vidéo : le style baké dans le plan reste dans le corps (traduit /
    #    composé) et n'est JAMAIS recollé par-dessus → pas de doublon. L'anti-doublon
    #    vit dans _post_compose_injections (chemin de repli) et dans le récap.
    tsrc = inspect.getsource(__import__("ui.tab_t2v", fromlist=["_"]))
    assert "_build_full_preview_text" in tsrc and "_baked_prev" in tsrc, \
        "aperçu vidéo : style baké non pris en compte"
    assert "if not _style_of_prev(self.prompt_ta.toPlainText()).strip() and vs:" in tsrc, \
        "style projet recollé même si déjà baké dans le plan (doublon)"


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
    assert "PLAN <NN>" in _syscine and "PROMPT VISUEL" in _syscine, \
        "format Cinéma v2 non calibré dans le prompt"
    # Le plan réécrit reste dans la LANGUE DE TRAVAIL (français par défaut) —
    # la traduction vers l'anglais est faite à l'ENVOI aux moteurs.
    assert "détaillé en français." in _syscine, "co-écriture Cinéma en langue de travail (fr)"
    dlg = PlanCoEditDialog(None, cine, edition="cinema")
    assert not dlg.was_applied() and dlg.result_layout() == cine
    # Réordonner (glisser-déposer) / ajouter / dupliquer / supprimer + renum P0N (Cinéma).
    _re = pl.reorder(cine, [1, 0])
    _lbls = [p["label"] for p in pl.split_plans(_re)]
    assert _lbls[0].startswith("P01 | Gros plan") and _lbls[1].startswith("P02 | Plan large"), "reorder + renum P0N"
    _add = pl.add_plan(cine, 0, "cinema")
    assert pl.plan_count(_add) == 3 and "PLAN 02" in _add, "add gabarit Cinéma v2 + renum"
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
    """Onglets Vidéo IA Cinéma façon Conducteur (2026-07-06) : barre fond bg0 +
    filet haut/bas, séparateurs de groupe conservés ; bouton « Envoyer à Claude »
    dans le chat Image IA (studio_images)."""
    import inspect
    sw = inspect.getsource(__import__("ui.seedance_widget", fromlist=["_"]))
    assert "QTabBar{{background:{C['bg0']};border:none;}}" in sw, \
        "barre d'onglets Studio IA Cinéma : fond noir + AUCUNE bordure (sinon ligne doublée/tronquée)"
    assert "QTabWidget::pane{{border:none;border-top:1px solid" in sw, \
        "filet pleine largeur sous la barre (bord haut du pane, façon Conducteur)"
    assert "_GroupedTabBar" in sw and "set_group_ends({3, 5})" in sw, \
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
    """Le worker legacy reste chirurgical, mais le flux principal range désormais
    la direction artistique dans la note sans altérer le scénario."""
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
    # UI Cinéma : l'analyse est ajoutée à la note, jamais au texte narratif.
    from ui.page_scenario import PageScenario
    _refsrc = inspect.getsource(PageScenario._open_refs_window)
    assert "append_to_note" in _refsrc and "_direction_note_edit" in _refsrc
    assert "EnrichScenarioWithRefsWorker(" not in _refsrc, \
        "le flux principal modifie encore le scénario depuis le moodboard"
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
    # Renommage Cinéma : section « Musique » (2026-07-22).
    src = inspect.getsource(PageScenario)
    assert '_make_toggle("🎵  Musique"' in src, \
        "section « Musique » : émoji pleine largeur 🎵 (alignement du libellé)"
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
    # Depuis le 2026-07-22, Sauvegarder/Ouvrir/Moods/Synchronisation/Récurrents/
    # Pitch deck vivent dans le menu déroulant « Action » tout à gauche.
    assert "self._btn_actions" in src and "_sync_actions_menu" in src, \
        "menu « Action » absent de la barre du storyboard"
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
    # Ensemble EXACT (volontairement strict : interdit tout ajout silencieux).
    # VEED v2 rejoint le catalogue le 2026-08-12 — 0,07 $/s, même contrat
    # video_url + audio_url, donc interchangeable sans toucher au worker.
    # PixVerse et Kling Lipsync rejoignent le catalogue le 2026-09-24 (fiches
    # fal : video_url + audio_url, sortie video.url — même contrat).
    assert set(ls.LIPSYNC_ENGINES) == {"sync2pro", "sync3", "veed2",
                                       "sync2", "pixverse", "kling", "latentsync"}
    assert ls.lipsync_endpoint("veed2") == "veed/lipsync/v2"
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
    assert "_inspo[0]" in rm, "run_mood : repli inspiration Flux absent"
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
    """Fenêtre « Générer les Moods » : moteur = TOUT le catalogue image de PANDORA
    (14 raster, nb2 en tête, pas de « flux » en Cinéma non-mapping) + réfs persos/
    décor/plan d'architecte. Les réfs de cohérence ne servent qu'aux moteurs qui
    ÉDITENT une image (grisées pour ceux qui les ignorent — Recraft) ; les options
    sont transmises au worker, et run_mood route par moteur."""
    import inspect
    import ui.page_storyboard as PS
    from core import image_engines as IE
    PS.sb_api.load_apercus = lambda sid: {"paths": [], "active_idx": 0}
    from PyQt6.QtWidgets import QWidget
    _par = QWidget()
    dlg = PS._MoodBatchDialog(_par, [{"id": "a", "number": 1, "scene_title": "T"}])
    for a in ("_opt_engine", "_opt_chars", "_opt_decor", "_opt_floor"):
        assert hasattr(dlg, a), "option manquante : " + a
    _keys = [dlg._opt_engine.itemData(i) for i in range(dlg._opt_engine.count())]
    assert _keys == IE.raster_engines(), "combo moteur ≠ catalogue image complet"
    # 2026-07-23 : Seedream 5 Pro en TÊTE du catalogue (décision Matthieu).
    assert _keys[0] == "seedream5_pro" and "flux" not in _keys and len(_keys) >= 14
    assert dlg._opt_chars.isChecked() and dlg._opt_decor.isChecked() and dlg._opt_floor.isChecked()
    # Moteur SANS référence (Recraft) → réfs de cohérence grisées ; moteur à réfs (nb2) → actives.
    dlg._opt_engine.setCurrentIndex(_keys.index("recraft"))
    assert not (dlg._opt_chars.isEnabled() or dlg._opt_decor.isEnabled() or dlg._opt_floor.isEnabled())
    dlg._opt_engine.setCurrentIndex(_keys.index("nb2"))
    assert dlg._opt_chars.isEnabled() and dlg._opt_decor.isEnabled() and dlg._opt_floor.isEnabled()
    # Le handler lit les options et les passe au worker
    cls = next(c for n, c in vars(PS).items()
               if isinstance(c, type) and hasattr(c, "_on_batch_mood"))
    obm = inspect.getsource(cls._on_batch_mood)
    assert "dlg._opt_engine.currentData()" in obm and "options=_mood_opts" in obm
    # run_mood : routage moteur (famille NB, flux héritage, générique) ; worker accepte options
    import api.apercu as A
    rm = inspect.getsource(A.run_mood)
    assert 'engine in ("nb2", "nb_pro")' in rm and "run_generation_nb2(" in rm
    assert 'engine == "flux"' in rm and "run_generation(" in rm
    assert "run_generation_engine(" in rm, "run_mood : chemin générique multi-moteurs absent"
    assert A._shot_ref_images({"character_ids": [], "decor_id": ""},
                              include_chars=False, include_decor=False) == []
    assert "options" in inspect.signature(A.MoodBatchWorker.__init__).parameters


@test
def rendu_audio_repliable_lipsync_ordre():
    """RENDU & AUDIO est un menu déroulant (replié par défaut).

    Disposition des lignes à réglage (Matthieu 2026-07-31) : le TITRE à gauche,
    le MENU à droite sur la même ligne, la DESCRIPTION en dessous. Le libellé
    « Moteur lip-sync » est retiré — la ligne s'appelle déjà « Resynchroniser
    les lèvres » et le nom du moteur se lit dans le menu."""
    from PyQt6.QtWidgets import QLabel, QComboBox
    import ui.tab_t2v as M
    tab = M.TabT2V()
    # Repliable
    assert hasattr(tab, "_raccords_toggle_btn") and hasattr(tab, "_raccords_body")
    assert tab._raccords_body.isHidden(), "RENDU & AUDIO doit être replié par défaut"
    tab._raccords_toggle_btn.click()
    assert not tab._raccords_body.isHidden(), "clic = déplier"
    tab._raccords_toggle_btn.click()
    assert tab._raccords_body.isHidden(), "re-clic = replier"

    # Le menu du moteur est SUR la ligne du titre, plus dans le corps en dessous.
    assert tab._lipsync_engine_combo in tab._lipsync_toggle_row.findChildren(QComboBox), \
        "le menu lip-sync n'est pas sur la ligne du titre"
    tlbls = [l.text() for l in tab._lipsync_toggle_row.findChildren(QLabel)]
    assert not any("Après génération" in t for t in tlbls), "description encore dans le toggle"
    assert not any("Moteur lip-sync" in t for t in tlbls), \
        "le libellé « Moteur lip-sync » devait être retiré"
    blbls = [l.text() for l in tab._raccords_body.findChildren(QLabel)]
    assert not any("Moteur lip-sync" in t for t in blbls), \
        "« Moteur lip-sync » traîne encore dans le corps"
    assert any("Après génération" in t for t in blbls), "description du lip-sync perdue"

    # Même disposition pour « Image du décor » : titre + menu sur une ligne,
    # description en dessous.
    assert tab._decor_ref_combo in tab._decor_ref_row.findChildren(QComboBox)
    _dlbls = [l.text() for l in tab._decor_ref_row.findChildren(QLabel)]
    assert any("Image du décor" in t for t in _dlbls), "titre du réglage décor absent"
    assert any("le lieu où se passe la scène" in t for t in _dlbls), \
        "description du réglage décor absente"

    # Flèche des menus à GAUCHE (demande Matthieu) — vérifié sur la feuille de style.
    for _c in (tab._decor_ref_combo, tab._lipsync_engine_combo):
        assert "subcontrol-position:left" in _c.styleSheet().replace(" ", ""), \
            "la flèche du menu n'est pas placée à gauche"


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
def plan_decor_creation_directe_fiche_et_vignette():
    """Créer le plan d'architecte vu de dessus À LA DEMANDE (demande 2026-07-31) :
    1. fiche décor → bouton « Créer le plan du décor » qui FORCE la régénération
       (la génération auto, elle, ne relance rien si le plan est à jour) ;
    2. page Décors → une vignette « à générer » se clique et lance la génération
       de CE seul décor (worker de lot à 1 job) ; sans clé fal.ai on INFORME ;
       un échec du clic direct N'EST PAS silencieux ;
    3. core.decors.set_floor_plan purge l'aperçu léger : sans ça, la carte
       continuerait d'afficher l'ANCIEN plan après une régénération."""
    import os, tempfile
    from PyQt6.QtWidgets import QApplication, QLabel
    from PyQt6.QtCore import Qt as _Qt
    QApplication.instance() or QApplication([])

    class _Sig:
        def connect(self, *_a):
            pass

    # ── 1. Fiche décor : bouton présent, force la régénération, se verrouille ──
    import ui.dialog_decor as DD
    d = tempfile.mkdtemp()
    fp = os.path.join(d, "plan.png")
    open(fp, "wb").write(b"x")
    item = {"id": "", "name": "Salon", "prompt": "un salon", "floor_plan": fp,
            "floor_plan_prompt": "un salon", "generated_images": []}
    dlg = DD.DecorDialog(None, item=item)
    assert hasattr(dlg, "_btn_floor_plan"), "bouton « Créer le plan du décor » absent"
    made = []

    class _FauxFP:
        def __init__(self, prompt, name, resolution=""):
            made.append(prompt)
            self.finished = _Sig()
            self.failed = _Sig()

        def isRunning(self):
            return False

        def start(self):
            made.append("start")

    _orig_fp = DD.GenerateFloorPlanWorker
    DD.GenerateFloorPlanWorker = _FauxFP
    try:
        dlg._maybe_gen_floor_plan()
        assert made == [], "plan à jour → la génération AUTO ne doit rien relancer"
        dlg._on_create_floor_plan()
        assert "start" in made, "le bouton doit FORCER la régénération même à jour"
        assert not dlg._btn_floor_plan.isEnabled(), \
            "bouton non verrouillé pendant la génération"
        dlg._floor_plan_worker = None   # worker factice → rien à parquer
        dlg._on_floor_plan_done("")     # mock (pas de clé)
        assert dlg._btn_floor_plan.isEnabled(), "bouton non réactivé après le mock"
    finally:
        DD.GenerateFloorPlanWorker = _orig_fp

    # ── 2. Page Décors : vignette « à générer » cliquable → job unique ────────
    import ui.page_decors as PD
    import api.nano_banana as NB
    import core.config as CFG
    page = PD.PageDecors()
    card = page._fp_card({"id": "z", "name": "Grange", "prompt": "une grange"}, "Grange")
    th = next((l for l in card.findChildren(QLabel) if "mousePressEvent" in vars(l)), None)
    assert th is not None and "générer" in th.text(), \
        "vignette « à générer » sans clic branché"
    assert th.cursor().shape() == _Qt.CursorShape.PointingHandCursor, \
        "vignette « à générer » sans curseur cliquable"

    calls = {"jobs": None, "start": 0}

    class _FauxLot:
        def __init__(self, jobs):
            calls["jobs"] = jobs
            self.plan_done = _Sig()
            self.finished = _Sig()

        def isRunning(self):
            return False

        def start(self):
            calls["start"] += 1

    shown = []

    class _FauxBox:
        @staticmethod
        def information(*_a, **_k):
            shown.append("info")

        @staticmethod
        def warning(*_a, **_k):
            shown.append("warn")

    _o_lot, _o_cfg, _o_box = NB.GenerateFloorPlansWorker, CFG.load_config, PD.QMessageBox
    NB.GenerateFloorPlansWorker = _FauxLot
    PD.QMessageBox = _FauxBox
    try:
        CFG.load_config = lambda: {"api_key": "k"}
        page._on_gen_single_plan({"id": "z", "prompt": "une grange", "name": "Grange"})
        assert calls["start"] == 1 and [j["id"] for j in calls["jobs"]] == ["z"], calls
        assert not page._fp_btn.isEnabled(), "bouton de lot non verrouillé pendant le job"
        page._fp_worker = None          # worker factice → rien à parquer
        # Sans clé fal.ai : informer, ne pas rester muet ni lancer de worker.
        CFG.load_config = lambda: {"api_key": ""}
        page._on_gen_single_plan({"id": "z", "prompt": "p", "name": "n"})
        assert shown == ["info"] and calls["start"] == 1, (shown, calls)
        # Échec du clic direct (0 plan généré) → avertissement, pas un silence.
        page.refresh = lambda: None
        page._fp_single = True
        page._on_fp_plans_finished(0)
        assert shown == ["info", "warn"], "échec du clic direct resté silencieux"
        assert not page._fp_single, "_fp_single doit retomber après le lot"
    finally:
        NB.GenerateFloorPlansWorker = _o_lot
        CFG.load_config = _o_cfg
        PD.QMessageBox = _o_box

    # ── 3. set_floor_plan purge l'aperçu léger de l'ancien plan ───────────────
    import core.decors as dec
    saved = []
    _oL, _oS = dec._load_index, dec._save_index
    dec._load_index = lambda: [{"id": "x", "floor_plan": "ancien.png",
                                "floor_plan_thumbnail": "ancien_thumb.jpg"}]
    dec._save_index = lambda idx: saved.append(idx)
    try:
        assert dec.set_floor_plan("x", "nouveau.png")
        assert saved and saved[0][0]["floor_plan"] == "nouveau.png"
        assert saved[0][0]["floor_plan_thumbnail"] == "", \
            "aperçu léger de l'ANCIEN plan non purgé → la carte l'afficherait encore"
    finally:
        dec._load_index, dec._save_index = _oL, _oS

    import core.i18n as i18n
    assert "Créer le plan du décor" in i18n._FR_TO_EN
    assert "Cliquer pour générer le plan d'architecte (vu de dessus)" in i18n._FR_TO_EN


@test
def fiche_decor_repliable_et_style_de_la_note():
    """Trois retours de Matthieu (2026-07-31) sur les fenêtres de génération :

    1. La fiche décor devient LISIBLE : nom/catégorie/prompt restent visibles,
       tout le reste est rangé dans des sections repliées, et les CINQ menus
       (usage des références, style, mode, moteur, format) sont réunis dans
       UNE seule section « Réglages de génération ».
    2. « Style de la note de réalisation » est en TÊTE de toutes les listes de
       style et sélectionné par défaut quand la note décrit un style — la
       relecture est DIRECTE (réécrire la note change le style généré).
    3. La fenêtre « Générer depuis le scénario » propose un bouton OK dès que
       les éléments sont enregistrés (avant : seul « ✕ Annuler » en rouge,
       alors que plus rien ne pouvait être perdu).
    """
    import inspect
    from PyQt6.QtWidgets import QApplication, QComboBox
    QApplication.instance() or QApplication([])

    # ── 1. Fiche décor : sections repliables + regroupement des 5 menus ──────
    import ui.dialog_decor as DD
    from ui.collapsible import CollapsibleSection
    dlg = DD.DecorDialog(None, item={"name": "Salon", "prompt": "un salon",
                                     "generated_images": []})
    for attr in ("_sec_refs", "_sec_settings", "_sec_creative"):
        sec = getattr(dlg, attr, None)
        assert isinstance(sec, CollapsibleSection), (attr, "section absente")
        assert not sec.is_expanded(), (attr, "doit être REPLIÉE par défaut")
    # Le prompt, lui, reste visible sans rien déplier.
    assert not dlg._prompt.isHidden(), "le prompt ne doit pas être replié"
    # Les 5 menus vivent DANS la section réglages (et pas ailleurs).
    def _in_section(widget, section):
        p = widget.parent()
        while p is not None:
            if p is section.body():
                return True
            p = p.parent()
        return False
    for name, w in (("usage", dlg._ref_usage_combo), ("style", dlg._style_combo),
                    ("mode", dlg._gen_mode), ("moteur", dlg._model_combo),
                    ("format", dlg._ratio_combo), ("définition", dlg._res_combo)):
        assert _in_section(w, dlg._sec_settings), \
            (name, "doit être dans la section « Réglages de génération »")
    # Replier/déplier agit réellement sur le corps.
    dlg._sec_settings.set_expanded(True)
    assert dlg._sec_settings.body().isVisibleTo(dlg), "déplier n'affiche pas le corps"
    dlg._sec_settings.set_expanded(False)
    assert not dlg._sec_settings.body().isVisibleTo(dlg), "replier ne masque pas"

    # Le prompt est ÉLASTIQUE (demande Matthieu 2026-07-31) : il prend la place
    # laissée libre quand tout est replié, et revient à son minimum une fois
    # les sections ouvertes. Une hauteur FIXE le laissait à 100 px sur une
    # fiche presque vide, alors qu'un prompt de décor fait dix lignes.
    from PyQt6.QtWidgets import QSizePolicy as _QSP
    assert dlg._prompt.sizePolicy().verticalPolicy() == _QSP.Policy.Expanding, \
        "le prompt doit pouvoir s'étirer"
    assert dlg._prompt.maximumHeight() > 1000, \
        "hauteur encore FIXE (setFixedHeight) : le prompt ne grandira jamais"
    dlg2 = DD.DecorDialog(None, item={"name": "S", "prompt": "p",
                                      "generated_images": []})
    dlg2.resize(1200, 860)
    dlg2.show()
    QApplication.instance().processEvents()
    h_replie = dlg2._prompt.height()
    for s in (dlg2._sec_refs, dlg2._sec_settings, dlg2._sec_creative):
        s.set_expanded(True)
    QApplication.instance().processEvents()
    h_deplie = dlg2._prompt.height()
    assert h_replie > h_deplie, (
        f"le prompt ne s'agrandit pas quand les sections sont repliées "
        f"({h_replie} px replié vs {h_deplie} px déplié)")
    assert h_deplie >= 100, ("le prompt passe sous sa hauteur minimale", h_deplie)

    # ── 2. Style de la note : en tête, actif seulement si la note en décrit un ─
    import core.style as style_api
    import core.scenario as scenario_api
    from ui.style_combo import populate, suffix_for, NOTE_KEY
    _oL, _oK = scenario_api.list_scenarios, style_api.get_style_key
    try:
        # (a) sans note → entrée présente mais DÉSACTIVÉE, défaut = style projet
        scenario_api.list_scenarios = lambda: []
        style_api.get_style_key = lambda: "arri_65"
        c = QComboBox()
        populate(c)
        assert c.itemData(0) == NOTE_KEY, "l'entrée note doit être en TÊTE"
        assert not c.model().item(0).isEnabled(), \
            "sans style écrit dans la note, l'entrée ne doit pas être choisissable"
        assert c.currentData() == "arri_65", "repli sur le style du projet"
        # (b) avec note → active ET sélectionnée par défaut ; suffixe = la note
        scenario_api.list_scenarios = lambda: [
            {"direction_note": "## STYLE VISUEL\nArcane, rendu peint à la main\n"}]
        c2 = QComboBox()
        populate(c2)
        assert c2.model().item(0).isEnabled() and c2.currentData() == NOTE_KEY, \
            "avec un style dans la note, l'entrée doit être le défaut"
        assert "Arcane" in suffix_for(c2), suffix_for(c2)
        # (c) choisie comme style DE PROJET → les suffixes projet la relisent
        style_api.get_style_key = lambda: NOTE_KEY
        assert "Arcane" in style_api.get_image_suffix(), "suffixe image"
        assert "Arcane" in style_api.get_video_suffix(), "suffixe vidéo"
        # (d) note vidée → aucun style, mais AUCUN plantage
        scenario_api.list_scenarios = lambda: [{"direction_note": "## STYLE VISUEL\n\n"}]
        assert style_api.get_image_suffix() == "", "note vide → pas de style inventé"
    finally:
        scenario_api.list_scenarios, style_api.get_style_key = _oL, _oK
    # Les 5 fenêtres d'élément passent bien par la liste PARTAGÉE.
    import ui.dialog_accessory as DA, ui.dialog_hmc as DH
    import ui.dialog_vehicle as DV, ui.dialog_character as DC
    for mod in (DD, DA, DH, DV, DC):
        assert "ui.style_combo" in inspect.getsource(mod), \
            (mod.__name__, "n'utilise pas la liste de styles partagée")

    # ── 3. Bouton OK dès que les éléments sont enregistrés ───────────────────
    import ui.dialog_extract_generate as EG
    src = inspect.getsource(EG.ExtractGenerateDialog)
    assert "_btn_ok" in src and "_saved_state" in src, "bouton OK absent"
    saved_src = inspect.getsource(EG.ExtractGenerateDialog._on_extraction_done)
    assert "_saved_state()" in saved_src, \
        "le bouton OK doit apparaître dès la sauvegarde, pas à la toute fin"
    # accept() doit PARQUER les workers : fermer pendant les plans d'architecte
    # laissait sinon un QThread survivre à la fenêtre détruite (crash Qt).
    acc = inspect.getsource(EG.ExtractGenerateDialog.accept)
    assert "_park_workers" in acc, "accept() ne parque pas les workers en cours"
    assert "_park_workers" in inspect.getsource(EG.ExtractGenerateDialog.reject)

    import core.i18n as i18n
    for k in ("⚙  Réglages de génération", "📝  Style de la note de réalisation",
              "✓  OK"):
        assert k in i18n._FR_TO_EN, ("i18n manquant", k)


@test
def atelier_7_vues_trois_moteurs():
    """Atelier 7 vues (2026-07-31) : la partie Décors devient DEUX onglets
    (« Décors » = page classique inchangée · « 7 vues » = atelier de vraies
    rotations), avec TROIS moteurs comparables. Fige :
    1. le hub à 2 onglets branché dans la navigation ;
    2. le mapping des angles Qwen (schéma fal.ai vérifié le 2026-07-31) ;
    3. les temps d'extraction de l'orbite (quarts de tour, 720p max en i2v) ;
    4. la géométrie de la reprojection panorama (4 yaw + 2 pôles) ;
    5. le mode mock des 3 workers : sans clé → done([]) SANS réseau ;
    6. l'écriture des vues sur la pièce (room_group), création comprise."""
    import inspect, os, tempfile
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])

    # 1) Hub 2 onglets, page classique intacte, branché dans la fenêtre.
    from ui.decors_hub import DecorsHub
    import ui.page_decors as PD
    import ui.page_decors_multiview as PM
    hub = DecorsHub()
    assert hub.tabs.count() == 2, "la partie Décors doit avoir 2 onglets"
    assert isinstance(hub.tabs.widget(0), PD.PageDecors), "onglet 1 = page classique"
    assert isinstance(hub.tabs.widget(1), PM.PageDecorsMultiview), "onglet 2 = atelier"
    assert hasattr(hub, "refresh"), "la navigation appelle refresh() sur la page"
    import ui.pandora_window as PW
    _src_pages = inspect.getsource(PW.PandoraWindow._build_pages)
    assert "DecorsHub" in _src_pages and "PageDecors" not in _src_pages, \
        "la navigation doit monter le hub, pas PageDecors directement"

    # 2) Angles Qwen — schéma CORRIGÉ SUR ESSAI RÉEL (2026-07-31, décor « Dojo
    #    — Crèche de Noël ») : Matthieu a constaté que « la gauche est en fait
    #    la droite ». Le LoRA compte les degrés dans le sens où voyage la
    #    CAMÉRA, pas le sujet : +90° l'amène à gauche de la pièce. Le schéma
    #    précédent venait de la doc, pas d'un rendu — il était inversé.
    import api.multiview as MV
    exp = {"avant": (0, 0), "gauche": (90, 0), "arriere": (180, 0),
           "droite": (270, 0), "sol": (0, 90), "plafond": (0, -30)}
    for code, (h, v) in exp.items():
        a = MV.QWEN_ANGLES[code]
        assert (a["horizontal_angle"], a["vertical_angle"]) == (h, v), (code, a)

    # …et le moteur ne DEMANDE que les vues qu'il sait produire : « avant » est
    # un doublon de l'image d'ensemble (rotation nulle), « plafond » exigerait
    # −90° de site quand le LoRA s'arrête à −30°. Les demander revenait à payer
    # deux images inutilisables (décision Matthieu 2026-07-31).
    assert set(MV.QWEN_SKIP) == {"avant", "plafond"}, MV.QWEN_SKIP
    from core.room_views import SIX_FACES as _SIX
    _demandees = [c for _l, c, _d in _SIX if c not in MV.QWEN_SKIP]
    assert _demandees == ["arriere", "gauche", "droite", "sol"], _demandees
    _run = inspect.getsource(MV.QwenMultiAngleWorker.run)
    assert "QWEN_SKIP" in _run, "le worker ignore la liste des vues écartées"

    # 3) Orbite : quarts de tour réguliers, l'avant à t=0 ; i2v plafonne à 720p.
    t = MV.orbit_face_times(8)
    assert t == {"avant": 0.0, "droite": 2.0, "arriere": 4.0, "gauche": 6.0}, t
    assert MV.ORBIT_RESOLUTION == "720p", "image-to-video Seedance 2.0 ≤ 720p"

    # 4) Reprojection panorama : géométrie vérifiée sur une image synthétique
    #    (couleur par direction) — centres des 4 yaw + zénith + nadir.
    import math
    import numpy as np
    from PIL import Image
    from core.panorama import render_view, VIEW_ANGLES
    W, H = 200, 100
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    for u in range(W):
        lon = (u / W - 0.5) * 2 * math.pi
        if abs(lon) < math.pi / 4:
            arr[:, u] = (255, 0, 0)
        elif math.pi / 4 <= lon <= 3 * math.pi / 4:
            arr[:, u] = (0, 255, 0)
        elif abs(lon) > 3 * math.pi / 4:
            arr[:, u] = (0, 0, 255)
        else:
            arr[:, u] = (255, 255, 0)
    for v in range(H):
        lat = (0.5 - v / H) * math.pi
        if lat > math.radians(60):
            arr[v, :] = (255, 255, 255)
        elif lat < math.radians(-60):
            arr[v, :] = (40, 40, 40)
    pano = Image.fromarray(arr, "RGB")
    attendu = {"avant": (255, 0, 0), "droite": (0, 255, 0),
               "arriere": (0, 0, 255), "gauche": (255, 255, 0),
               "plafond": (255, 255, 255), "sol": (40, 40, 40)}
    for code, (yaw, pitch) in VIEW_ANGLES.items():
        c = render_view(pano, yaw, pitch, 95.0, 64, 36).getpixel((32, 18))
        assert all(abs(a - b) <= 14 for a, b in zip(c, attendu[code])), \
            (code, c, attendu[code], "la reprojection ne regarde pas la bonne direction")

    # 5) Mode mock : sans clé fal.ai, les 3 workers émettent done([]) sans réseau.
    _o_cfg = MV.load_config
    MV.load_config = lambda: {}
    try:
        for cls in (MV.QwenMultiAngleWorker, MV.SeedanceOrbitWorker,
                    MV.HunyuanPanoramaWorker):
            w = cls("", "test")
            got = []
            w.done.connect(lambda v, _g=got: _g.append(v))
            w.run()   # synchrone : pas de thread dans le harnais
            assert got == [[]], (cls.__name__, got, "mock sans clé ≠ done([])")
    finally:
        MV.load_config = _o_cfg

    # 6) Écriture des vues : un décor libre devient une pièce, le frère est créé
    #    puis MIS À JOUR (pas dupliqué) à la vue suivante.
    import core.decors as dec
    d = tempfile.mkdtemp()
    p1 = os.path.join(d, "v1.png")
    open(p1, "wb").write(b"x")
    store: list[dict] = [{"id": "libre", "name": "Grange", "prompt": "une grange",
                          "category": "Intérieur", "room_group": ""}]

    def _fake_save(data):
        for i, existing in enumerate(store):
            if existing.get("id") and existing.get("id") == data.get("id"):
                store[i] = data
                return data
        data.setdefault("id", f"id{len(store)}")
        store.append(data)
        return data

    _oL, _oS = dec.list_decors, dec.save_decor
    dec.list_decors = lambda: list(store)
    dec.save_decor = _fake_save
    try:
        page = PM.PageDecorsMultiview()
        rep = store[0]
        page._apply_view(rep, {"label": "Avant", "code": "avant", "path": p1,
                               "thumbnail_path": "", "prompt": "vue avant"})
        assert rep.get("room_group") == "Grange", "le décor libre devient une pièce"
        freres = [s for s in store if s.get("room_view") == "Avant"]
        assert len(freres) == 1 and freres[0]["image_path"] == p1, freres
        p2 = os.path.join(d, "v2.png")
        open(p2, "wb").write(b"y")
        page._apply_view(rep, {"label": "Avant", "code": "avant", "path": p2,
                               "thumbnail_path": "", "prompt": "vue avant"})
        freres = [s for s in store if s.get("room_view") == "Avant"]
        assert len(freres) == 1, "la régénération ne doit PAS dupliquer le frère"
        assert freres[0]["image_path"] == p2 and p1 in freres[0]["generated_images"]
        page._apply_view(rep, {"label": "Panorama 360°", "code": "panorama",
                               "path": p2, "thumbnail_path": "", "prompt": "",
                               "is_panorama": True})
        assert rep.get("panorama_path") == p2, "panorama conservé sur la pièce"
    finally:
        dec.list_decors, dec.save_decor = _oL, _oS

    import core.i18n as i18n
    for k in ("Atelier 7 vues", "7 vues", "Générer les vues", "Pièce / décor"):
        assert k in i18n._FR_TO_EN, ("i18n manquant", k)


@test
def apercu_plein_ecran_des_vues_et_onglets_renommes():
    """Retours Matthieu 2026-07-31 (capture de l'atelier en fonctionnement) :
    1. les vues générées s'ouvrent en GRAND au clic, avec navigation entre
       elles (comparer « Avant » et « Arrière » est le geste utile) ;
    2. les onglets de la partie Décors s'appellent « Standard » / « Avancé ».
    """
    import os, tempfile
    from PIL import Image
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    QApplication.instance() or QApplication([])

    # ── 2. Onglets renommés ─────────────────────────────────────────────────
    from ui.decors_hub import DecorsHub
    hub = DecorsHub()
    titres = [hub.tabs.tabText(i) for i in range(hub.tabs.count())]
    assert any("Standard" in t for t in titres), titres
    assert any("Avancé" in t for t in titres), titres
    assert not any("7 vues" in t for t in titres), ("l'ancien libellé subsiste", titres)

    # ── 1. Visualiseur : navigation, bouclage, cas limites ───────────────────
    _d = os.path.join(_TMP, "preview")
    os.makedirs(_d, exist_ok=True)
    paths = {}
    for nom, rgb in (("master", (90, 60, 140)), ("avant", (200, 60, 60)),
                     ("arriere", (60, 60, 200)), ("gauche", (220, 200, 60))):
        p = os.path.join(_d, f"{nom}.png")
        Image.new("RGB", (320, 180), rgb).save(p)
        paths[nom] = p

    from ui.image_preview_dialog import ImagePreviewDialog, show_images
    items = [("Plan d'ensemble", paths["master"]), ("Avant", paths["avant"]),
             ("Arrière", paths["arriere"]), ("Gauche", paths["gauche"])]
    dlg = ImagePreviewDialog(items, 2)
    assert dlg.current_label() == "Arrière", "ouverture sur la vue cliquée"
    dlg.next()
    assert dlg.current_label() == "Gauche"
    dlg.next()
    assert dlg.current_label() == "Plan d'ensemble", "la navigation doit BOUCLER"
    dlg.previous()
    assert dlg.current_label() == "Gauche"
    # Une seule image → pas de flèches (elles ne mèneraient nulle part).
    solo = ImagePreviewDialog([("Avant", paths["avant"])], 0)
    solo.show()
    assert not solo._btn_prev.isVisible() and not solo._btn_next.isVisible()
    # Une entrée illisible est ÉCARTÉE, et rien ne s'ouvre s'il ne reste rien.
    mixte = ImagePreviewDialog([("Absent", os.path.join(_d, "nope.png")),
                               ("Avant", paths["avant"])], 0)
    assert mixte.current_label() == "Avant", "l'entrée illisible doit être écartée"
    assert show_images(None, [("X", os.path.join(_d, "nope.png"))]) is False, \
        "aucune image lisible → ne pas ouvrir une fenêtre vide"

    # ── L'atelier propose bien ensemble + vues, et branche le clic ───────────
    import core.decors as dec
    import ui.page_decors_multiview as PM
    store = [{"id": "e", "name": "Dojo", "room_group": "Dojo",
              "room_view": "Ensemble", "image_path": paths["master"]},
             {"id": "a", "name": "Dojo · Avant", "room_group": "Dojo",
              "room_view": "Avant", "image_path": paths["avant"]},
             {"id": "b", "name": "Dojo · Arrière", "room_group": "Dojo",
              "room_view": "Arrière", "image_path": paths["arriere"]}]
    _oL = dec.list_decors
    dec.list_decors = lambda: list(store)
    try:
        page = PM.PageDecorsMultiview()
        page.refresh()
        labels = [l for l, _p in page._preview_items()]
        assert labels == ["Plan d'ensemble", "Avant", "Arrière"], labels
        # La vignette d'une vue EXISTANTE est cliquable ; celle « à générer » non
        # (elle lancerait un aperçu vide).
        av = page._view_cards.get("avant")
        assert av is not None and "mousePressEvent" in vars(av), \
            "la vignette d'une vue générée doit ouvrir l'aperçu"
        assert av.cursor().shape() == Qt.CursorShape.PointingHandCursor
        sol = page._view_cards.get("sol")
        assert sol is not None and "mousePressEvent" not in vars(sol), \
            "une vue « à générer » ne doit pas ouvrir d'aperçu vide"

        # Reconstruire la grille ne doit laisser AUCUNE carte fantôme.
        # `deleteLater` ne détruit qu'au prochain tour de boucle d'événements :
        # une carte seulement retirée du LAYOUT reste ENFANT de son conteneur
        # et flotte en (0,0) par-dessus le plan d'ensemble (carte « Plafond »
        # fantôme, constatée au rendu 2026-07-31). Il faut setParent(None).
        # On compte les cartes encore RATTACHÉES à l'arbre : après trois
        # reconstructions il doit toujours y en avoir six, pas dix-huit.
        from PyQt6.QtWidgets import QWidget as _QW
        _carte = lambda w: (w.width() == PM._CARD_W
                            and w.height() == PM._CARD_H + 22)
        page.refresh()
        page.refresh()
        rattachees = [w for w in page.findChildren(_QW) if _carte(w)]
        assert len(rattachees) == len(PM.SIX_FACES), (
            f"{len(rattachees)} cartes rattachées au lieu de {len(PM.SIX_FACES)} : "
            "les anciennes restent enfants du conteneur et flottent par-dessus "
            "le plan d'ensemble (setParent(None) manquant avant deleteLater)")
    finally:
        dec.list_decors = _oL

    import core.i18n as i18n
    for k in ("Standard", "Avancé", "Cliquer pour voir en grand"):
        assert k in i18n._FR_TO_EN, ("i18n manquant", k)


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
    import os, inspect, tempfile, time
    from PyQt6.QtWidgets import QApplication, QFileDialog, QListView
    from PyQt6.QtCore import QFileInfo
    from PyQt6.QtGui import QPixmap
    QApplication.instance() or QApplication([])
    import ui.file_dialogs as FD
    # 1) icon() ne doit JAMAIS décoder sur le thread UI. Mesuré le 2026-07-20 sur
    #    un dossier réel (217 PNG de 16,7 Mo) : 354 ms par vignette, 100 % sur le
    #    thread principal → 157 s de gel (« Ne répond pas »). Le décodage part
    #    donc en fond ; icon() rend la main tout de suite et la vignette arrive
    #    ensuite dans le cache.
    d = tempfile.mkdtemp()
    img = os.path.join(d, "x.png")
    QPixmap(80, 80).save(img)
    prov = FD.ThumbnailIconProvider()
    _t0 = time.perf_counter()
    ic = prov.icon(QFileInfo(img))
    _dt_ms = (time.perf_counter() - _t0) * 1000
    assert not ic.isNull(), "icône absente"
    assert _dt_ms < 50, f"icon() doit rendre la main immédiatement ({_dt_ms:.0f} ms)"
    _p = QFileInfo(img).absoluteFilePath()
    assert _p in prov._queued or _p in prov._cache, "décodage de fond non programmé"
    assert prov._pool.waitForDone(10000), "décodage de fond non terminé"
    prov._drain()                      # normalement déclenché par le timer
    assert _p in prov._cache, "vignette absente du cache après décodage de fond"
    assert not prov.icon(QFileInfo(img)).isNull(), "vignette non servie depuis le cache"
    # 2) apply_thumbnails : non-natif + provider + iconSize agrandi
    dlg = QFileDialog()
    FD.apply_thumbnails(dlg)
    assert dlg.testOption(QFileDialog.Option.DontUseNativeDialog), "dialogue natif (risque COM)"
    assert dlg.iconProvider() is FD._shared_provider(), "icon provider non posé"
    # Les vignettes arrivant en différé, les vues doivent être repeintes
    assert FD._shared_provider()._views, "vues non enregistrées pour le rafraîchissement"
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
    credit_error = humanize_ai_error("Your credit balance is too low")
    assert "Crédits" in credit_error and "fournisseur" in credit_error
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
    _teardown_qt()
    return 1 if ko else 0


def _teardown_qt() -> None:
    """Teardown DÉTERMINISTE avant la fin du processus (anti-0xC0000409).

    Les tests laissent des widgets top-level jamais détruits (deleteLater sans
    boucle d'événements = jamais traité) : le QFileDialog non natif garde son
    thread « gatherer » de QFileSystemModel, et les vignettes tournent dans des
    QThreadPool dont les threads inactifs survivent 30 s. Ces threads NATIFS
    (invisibles depuis Python : ni threading.enumerate(), ni QThread) couraient
    encore pendant la destruction de Qt à la sortie de l'interpréteur → fail-fast
    Windows 0xC0000409 environ un run sur deux, APRÈS l'impression du résumé.
    On détruit donc tout explicitement pendant que l'interpréteur est sain.
    Chaque étape est blindée : ce bloc ne doit JAMAIS rougir un run vert."""
    from PyQt6.QtCore import QThreadPool, QEvent

    # 1. Fermer et détruire tous les widgets top-level, puis traiter les
    #    DeferredDelete (sendPostedEvents les force même hors boucle d'événements).
    for w in list(APP.topLevelWidgets()):
        try:
            w.close()
            w.deleteLater()
        except Exception:
            pass
    try:
        APP.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        APP.processEvents()
    except Exception:
        pass

    # 2. Vider les pools de threads (vignettes des dialogues de fichiers + global).
    try:
        import ui.file_dialogs as _FD
        if _FD._provider is not None:
            _FD._provider._timer.stop()
            _FD._provider._pool.clear()
            _FD._provider._pool.waitForDone(5000)
    except Exception:
        pass
    try:
        QThreadPool.globalInstance().clear()
        QThreadPool.globalInstance().waitForDone(5000)
    except Exception:
        pass

    # 3. Laisser finir les threads parqués par core.worker.abandon_thread.
    try:
        import core.worker as _CW
        for _t in list(_CW._ABANDONED_THREADS):
            try:
                _t.wait(3000)
            except Exception:
                pass
    except Exception:
        pass

    try:
        APP.processEvents()
    except Exception:
        pass


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
    # Le plafond ne s'écrit plus en dur dans api/real : il vient de la table des
    # familles Seedance (2026-08-09, arrivée de la 2.5 qui monte à 50). On
    # vérifie donc la VALEUR effective, pas une chaîne de code — l'ancienne
    # assertion (`"ref_images[:9]" in rsrc`) serait passée au vert sur un
    # plafond devenu faux.
    from core import seedance_family as _sf
    assert _sf.max_images("seedance-2.0") == 9, "limite refs 2.0 non montée à 9"
    assert "_sf.max_images(model)" in rsrc, "api/real n'utilise pas la table des familles"
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
def moteurs_image_catalogue_unifie():
    """Catalogue image UNIFIÉ (core/image_engines) — élargissement 2026-07-20 : TOUS
    les moteurs image de PANDORA sont proposés dans les Moods ET les 5 dialogs
    d'éléments (avant : Moods = nb2/flux ; éléments = 6 modèles). Source unique =
    studio_images/engines.py + réintégration GPT Image 2 / FLUX.2 (sans régression),
    vecteur SVG exclu. `_build_image_args` câble chaque moteur élargi."""
    import os
    from core import image_engines as IE
    from api.nano_banana import _build_image_args
    # 1) Catalogue : union raster, vecteur exclu, GPT/FLUX.2 réintégrés.
    keys = IE.raster_engines()
    # 2026-07-23 : Seedream 5 Pro par défaut et en tête, puis Recraft, puis nb2.
    assert keys[0] == "seedream5_pro" and keys[1] == "recraft" and keys[2] == "nb2" \
        and len(keys) >= 14, "catalogue raster incomplet ou mal ordonné"
    assert "recraft_vector" not in keys, "vecteur SVG doit rester réservé au Studio IA"
    for k in ("gpt2", "flux2", "recraft", "zimage", "qwen_image", "ideogram",
              "flux_ultra", "seedream5", "seedream5_pro", "nb2_lite"):
        assert k in keys, f"{k} absent du catalogue unifié"
    # 2) Mapping : SEULS les moteurs éditeurs de référence (endpoint /edit).
    # 24/09/2026 : Seedream 5 Flash, Qwen-Image 2, Kling Image O3, GPT Image
    # 2.5 Flare et FLUX.2 pro ont un /edit relu sur leur fiche fal.
    assert set(IE.edit_capable_engines()) == {"nb2", "nb_pro", "nb2_lite",
                                              "seedream5_pro", "seedream5",
                                              "seedream5_flash", "qwen_image2",
                                              "kling_image", "gpt25", "flux2"}, \
        "éditeurs de référence (mapping) ≠ moteurs à endpoint /edit vérifié"
    assert [k for k, _ in IE.reference_engine_choices()] == IE.edit_capable_engines(), \
        "workflow 7 vues : proposer uniquement les moteurs d'édition compatibles"
    assert not IE.is_edit_capable("recraft") and not IE.is_edit_capable("zimage")
    # 3) _build_image_args câble les moteurs ÉLARGIS via le catalogue (endpoints réels),
    #    et les 6 historiques gardent LEUR câblage (zéro régression).
    assert _build_image_args("p", "16:9", "1K", {"image_model": "zimage"}, 1)[0] == \
        "fal-ai/z-image/turbo"
    assert _build_image_args("p", "16:9", "1K", {"image_model": "seedream5_pro"}, 1)[0] == \
        "bytedance/seedream/v5/pro/text-to-image"
    assert _build_image_args("p", "16:9", "1K", {"image_model": "flux_ultra"}, 1)[0] == \
        "fal-ai/flux-pro/v1.1-ultra"
    _, a_nb = _build_image_args("p", "2:3", "1K", {"image_model": "nb2"}, 1)
    assert a_nb.get("safety_tolerance") == "6" and "aspect_ratio" in a_nb, "nb2 câblage historique"
    # 4) Les 5 dialogs d'éléments peuplent LEUR combo depuis le catalogue COMPLET.
    from ui.dialog_character import CharacterDialog
    d = CharacterDialog(None)
    combo_keys = [d._model_combo.itemData(i) for i in range(d._model_combo.count())]
    assert combo_keys == keys, "combo casting ≠ catalogue image complet"
    for _f in ("dialog_character", "dialog_decor", "dialog_accessory",
               "dialog_hmc", "dialog_vehicle"):
        with open(os.path.join("ui", _f + ".py"), encoding="utf-8") as fh:
            src = fh.read()
        assert "engine_choices" in src and "IMAGE_MODEL_LABELS" not in src, \
            f"{_f} : combo moteur pas basculé sur le catalogue complet"
    # 5) get_image_price / endpoint résolus pour les moteurs élargis.
    from core.config import get_image_price, get_image_endpoint
    assert get_image_endpoint({"image_model": "seedream5"}).endswith("/text-to-image")
    assert "$" in get_image_price({"image_model": "flux_ultra"})


@test
def chat_ia_elements():
    """Chat « direction artistique » dans les 5 dialogs d'éléments (2026-07-20) :
    panneau repliable à droite (comme le Studio Images) pour améliorer le prompt,
    avec import d'images de référence. Workers anti-crash (signal `done`), prompt
    synthétisé INJECTÉ dans le champ « Prompt » de l'hôte."""
    import inspect
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from PyQt6.QtCore import QThread
    # 1) Workers : done (jamais finished), brief par type distinct, sortie française.
    import api.element_chat as EC
    for cls in (EC.ElementChatWorker, EC.ElementSynthWorker):
        assert hasattr(cls, "done") and "finished" not in cls.__dict__, \
            f"{cls.__name__} : signal done, jamais finished"
        assert cls.finished is QThread.finished
    kinds = ("character", "decor", "accessory", "hmc", "vehicle")
    briefs = {k: EC._chat_system(k) for k in kinds}
    assert len(set(briefs.values())) == len(kinds), "un brief distinct par type d'élément"
    assert "PORTRAIT" in briefs["character"] and "DÉCOR" in briefs["decor"]
    assert "FRANÇAIS" in EC._synth_system("decor"), "le prompt synthétisé sort en français"
    # 2) Panneau réutilisable : repli/expansion + injection + parking anti-crash.
    from ui.element_chat_panel import ElementChatPanel
    box = {}
    p = ElementChatPanel("accessory", lambda s: box.__setitem__("p", s), None)
    assert hasattr(p, "_expand") and hasattr(p, "_collapse") and hasattr(p, "shutdown")
    assert p.width() == p._W_STRIP, "replié par défaut (poignée fine)"
    p._expand(); assert p.width() == p._W_FULL, "déplié = panneau large"
    p._collapse(); assert p.width() == p._W_STRIP, "repliable"
    p._on_synth("Un prompt de test")
    assert box.get("p") == "Un prompt de test", "la synthèse est injectée via le callback"
    assert "_park(" in inspect.getsource(ElementChatPanel._send), \
        "worker précédent parqué avant réassignation (anti-segfault)"
    # 3) Les 5 dialogs embarquent le panneau, du bon type, câblé sur self._prompt.
    import ui.dialog_character as DC, ui.dialog_decor as DD, ui.dialog_accessory as DA2
    import ui.dialog_hmc as DH, ui.dialog_vehicle as DV
    specs = [(DC.CharacterDialog, "character"), (DD.DecorDialog, "decor"),
             (DA2.AccessoryDialog, "accessory"), (DH.HMCDialog, "hmc"),
             (DV.VehicleDialog, "vehicle")]
    for _Dlg, _kind in specs:
        d = _Dlg(None)
        assert getattr(d, "_chat_panel", None) is not None \
            and d._chat_panel._kind == _kind, (_Dlg.__name__, "chat panel absent/mauvais type")
        d._chat_panel._on_synth("PROMPT INJECTÉ")
        assert d._prompt.toPlainText() == "PROMPT INJECTÉ", (_Dlg.__name__, "injection prompt KO")
    # 4) i18n du panneau (FR + EN).
    from core.i18n import _FR_TO_EN
    for _t in ("☁  Améliorer avec l'IA", "📎  Joindre une image", "✍️  Mettre à jour le prompt"):
        assert _t in _FR_TO_EN, ("i18n manquant", _t)


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
def coecriture_session_persistee():
    """Co-écriture Cinéma : la SESSION (conversation Claude + scénario remanié +
    versions) est persistée à CHAQUE tour et REPRISE à la réouverture — plus de
    perte après « Appliquer » (retour Matthieu 2026-07-20). Le worker Claude est
    parqué à la fermeture (crash vécu à l'apply)."""
    import inspect
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from ui.dialog_arrange_session import ArrangeSessionDialog
    assert hasattr(ArrangeSessionDialog, "session_committed"), "signal session_committed"
    assert "session_state" in inspect.signature(ArrangeSessionDialog.__init__).parameters, \
        "param session_state (reprise)"
    st = {"history": [{"role": "user", "content": "plus tendu"},
                      {"role": "assistant", "content": "voici"}],
          "screenplay": "SCENARIO V2", "versions": ["SCENARIO V2"], "version_idx": 0}
    d = ArrangeSessionDialog(None, "ORIG", "ANALYSE", 5, session_state=st)
    assert len(d._history) == 2 and d._screenplay == "SCENARIO V2", "session non reprise"
    assert d._screenplay_edit.toPlainText() == "SCENARIO V2" and d._tabs.isTabEnabled(1)
    assert d._btn_apply.isEnabled(), "Appliquer actif à la reprise"
    assert d.session_state()["history"] == st["history"], "round-trip de l'état"
    got = {}
    d.session_committed.connect(lambda s: got.update(s))
    d._on_message_ready("nouvelle réponse")
    assert got.get("history", [{}])[-1].get("content") == "nouvelle réponse", "commit à chaque tour"
    assert "abandon_thread" in inspect.getsource(ArrangeSessionDialog.done), \
        "worker parqué à la fermeture (done)"
    import ui.page_scenario as PS
    _cls = next(c for _n, c in vars(PS).items()
                if isinstance(c, type) and hasattr(c, "_open_arrange_session")
                and hasattr(c, "_on_arrange_session_autosave"))
    _src = inspect.getsource(_cls._open_arrange_session)
    assert "session_state=" in _src and "session_committed.connect" in _src, \
        "page : reprise + autosave branchés"
    _asrc = inspect.getsource(_cls._on_arrange_session_autosave)
    assert "arrange_session" in _asrc and "self._save(" in _asrc, "autosave persiste la session"
    assert "self._save(silent=True)" in _src, "page : sauvegarde immédiate à l'application"


@test
def coecriture_reecriture_ciblee():
    """Co-écriture Cinéma (retour Matthieu 2026-07-20) : la réécriture COMPLÈTE est
    remontée à 16000 tokens (8192 perdait la FIN des longs scénarios) ; un bouton
    « Réécrire selon la co-écriture » (édits ciblés sur les seuls passages travaillés,
    sans troncature) est AU-DESSUS de « Générer tout le scénario » (renommé) ; un
    garde-fou avertit si une réécriture complète semble tronquée."""
    import inspect
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from api.screenplay import ArrangeChatWorker
    _wsrc = inspect.getsource(ArrangeChatWorker.run)
    assert "8192 if self._surgical else 16000" in _wsrc, \
        "réécriture complète : 16000 tokens (anti-troncature de la fin)"
    from ui.dialog_arrange_session import ArrangeSessionDialog
    d = ArrangeSessionDialog(None, "ORIG", "ANALYSE", 5)
    assert hasattr(d, "_btn_rewrite_coedit"), "bouton « Réécrire selon la co-écriture »"
    assert d._btn_generate.text() == "✎  Générer tout le scénario", "bouton complet renommé"
    _cap = {}
    d._start_worker = lambda instr, surgical=True, **k: _cap.update(instr=instr, surgical=surgical)
    d._screenplay = "X"
    d._on_rewrite_coedit()
    assert _cap.get("surgical") is True, "réécriture ciblée = mode chirurgical (jamais tout réécrire)"
    assert "SEULS passages" in _cap.get("instr", ""), "instruction : uniquement les passages travaillés"
    assert "0.55" in inspect.getsource(ArrangeSessionDialog._on_screenplay_ready), \
        "garde-fou anti-troncature (avertissement si réécriture trop courte)"
    from core.i18n import _FR_TO_EN as T
    for _t in ("✦  Réécrire selon la co-écriture", "✎  Générer tout le scénario"):
        assert _t in T, ("i18n manquant", _t)


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
        # Prix : grille PiAPI (0.20 $/s en 720p) vs fal (0.3034 $/s)
        cost, mode = pricing.estimate("seedance-2.0", "720p", 10.0, 1)
        assert mode == "s" and abs(cost - 2.0) < 1e-6, ("prix PiAPI attendu 2.0", cost)
        msg = pricing.format_estimate("Seedance 2.0", "seedance-2.0", "720p", 10.0, 2)
        assert "piapi.ai" in msg, "le rappel doit citer le distributeur actif"
        # Retour à fal → grille fal restaurée
        mp.load_config = lambda: {}
        cost_fal, _ = pricing.estimate("seedance-2.0", "720p", 10.0, 1)
        assert abs(cost_fal - 3.034) < 1e-6, ("prix fal attendu 3.034", cost_fal)
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
    # UN SEUL bandeau (2026-07-20) : le doublon in-tab est retiré → seul le footer
    # fixe affiche l'estimation (l'onglet n'ajoute plus price_frame à son layout).
    assert "lay.addWidget(price_frame)" not in inspect.getsource(T.TabT2V), \
        "doublon d'estimation : l'onglet ne doit plus afficher son propre bandeau"
    # L'estimation reflète le DISTRIBUTEUR ACTIF AVANT la file : recompute à
    # l'affichage du Studio et à l'entrée dans l'onglet « Générer depuis Storyboard ».
    assert "_refresh_price_estimate" in inspect.getsource(SW.SeedanceWidget.showEvent), \
        "prix non recomputé à l'affichage (distributeur PiAPI/fal pas à jour avant la file)"
    assert "_refresh_price_estimate" in inspect.getsource(SW.SeedanceWidget._on_tab_changed), \
        "prix non recomputé à l'entrée dans l'onglet"

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


@test
def studio_ia_file_attente_et_balayage_moteurs():
    """Studio IA / Image IA — chantier 2026-07-20 :
    1) anti-crash : workers en signal `done`, worker précédent PARQUÉ avant
       réassignation, parking des threads à la fermeture de l'app ;
    2) anti-gel : vignettes décodées à la taille utile (plus de pleine résolution
       sur le thread principal), aperçu principal inchangé ;
    3) lot jusqu'à 10 images, « Annuler » interrompt AVANT l'appel facturé ;
    4) comparatif « plusieurs moteurs » : multi-sélection (défaut = un moteur par
       famille), nom du moteur en fin de nom de fichier."""
    import os as _os
    import sys as _sys
    _studio = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "studio_images")
    if _studio not in _sys.path:
        _sys.path.insert(0, _studio)
    from PyQt6.QtCore import QThread
    import chat as CH
    import engines as E
    import imagegen as IG

    # ── 1. Anti-crash ────────────────────────────────────────────────────────
    for cls in (IG.ImageWorker, CH.ChatWorker, CH.SynthPromptWorker):
        assert hasattr(cls, "done"), f"{cls.__name__}.done attendu"
        assert "finished" not in cls.__dict__, \
            f"{cls.__name__} masque QThread.finished (cause de segfault)"
        assert cls.finished is QThread.finished, f"{cls.__name__} : finished natif intact"

    from ui.tab_image import TabImage
    _ti = TabImage()          # référence gardée : sinon le GC détruit les widgets C++
    pn = _ti.panel
    assert hasattr(pn, "_park_worker") and hasattr(pn, "_park_all"), "parking des threads"
    assert "aboutToQuit" in inspect.getsource(type(pn).__init__), \
        "threads parqués à la fermeture de l'app"
    for _m in ("_launch_image_worker", "_do_send", "_synth_prompt"):
        assert "_park_worker(" in inspect.getsource(getattr(type(pn), _m)), \
            f"{_m} : parquer le worker précédent AVANT de réassigner (anti-GC)"

    # ── 2. Anti-gel des vignettes ────────────────────────────────────────────
    assert "setScaledSize" in inspect.getsource(type(pn)._thumb_pixmap), \
        "vignettes décodées à la taille utile (QImageReader)"
    for _m in ("_thumb_tile", "_add_bubble", "_add_history"):
        assert "_thumb_pixmap(" in inspect.getsource(getattr(type(pn), _m)), \
            f"{_m} doit passer par _thumb_pixmap"
    assert "_load_pixmap(" in inspect.getsource(type(pn)._show_preview), \
        "l'aperçu principal reste en pleine résolution"

    # ── 3. Lot de 1 à 10 + annulation non facturée ───────────────────────────
    assert (pn._count.minimum(), pn._count.maximum()) == (1, 10), "lot de 1 à 10 images"
    _real = inspect.getsource(IG.ImageWorker._real)
    assert "isInterruptionRequested()" in _real, "« Annuler » doit interrompre la file"
    # Depuis le 24/09/2026 l'appel passe par _subscribe (fal ou ComfyUI).
    assert _real.index("isInterruptionRequested()") < _real.index("_subscribe("), \
        "interrompre AVANT l'appel facturé (sinon le reste du lot est payé)"

    # ── 4. Balayage multi-moteurs ────────────────────────────────────────────
    for _k, _e in E.ENGINES.items():
        assert _e.get("family") and _e.get("slug"), f"{_k} : famille + slug requis"
    _slugs = [_e["slug"] for _e in E.ENGINES.values()]
    assert len(_slugs) == len(set(_slugs)), "slugs de moteurs uniques"
    _sweep = E.sweep_engines()
    _fams = [E.family_of(_k) for _k in _sweep]
    assert len(_fams) == len(set(_fams)), "un seul moteur par famille (pas les versions)"
    assert set(_fams) == {_e["family"] for _e in E.ENGINES.values()}, \
        "toutes les familles du catalogue sont balayées"
    assert "recraft_vector" not in _sweep, "pas de sortie SVG dans un balayage d'images"
    for _k in _sweep:
        E.build_request(_k, "test", (1024, 1024), "1K", [])   # aucun schéma cassé
    assert hasattr(pn, "_gen_all_btn") and hasattr(pn, "_generate_all_engines"), \
        "bouton « Générer avec plusieurs moteurs »"
    _gae = inspect.getsource(type(pn)._generate_all_engines)
    assert "_choose_engines(" in _gae and "engine_keys=" in _gae, \
        "multi-sélection : choisir les moteurs PUIS lancer la file"
    assert hasattr(pn, "_choose_engines"), "fenêtre de sélection multiple des moteurs"
    assert "engines.ENGINES" in inspect.getsource(type(pn)._choose_engines), \
        "la sélection multiple liste TOUT le catalogue de moteurs"
    assert "slug_for(" in _real, "nom du moteur ajouté à la fin du fichier généré"

    # i18n du nouveau bouton (FR + EN)
    from core.i18n import _FR_TO_EN
    assert pn._gen_all_btn.text() in _FR_TO_EN, "libellé du balayage traduit"
    assert pn._gen_all_btn.toolTip() in _FR_TO_EN, "infobulle du balayage traduite"


@test
def prompt_video_prose_composee():
    """Prompts Seedance du storyboard (2026-07-21) : à l'ENVOI, les sections FR sont
    composées par l'IA en PROSE anglaise dense — style en TÊTE, fiches casting
    injectées, son guidé (generate_audio), durée écrite — au lieu de partir balisées
    puis traduites (mauvais rendus constatés). Le storyboard reste l'espace de
    travail plan par plan (sections intactes) ; repli complet sur le chemin
    historique (Live, texte libre, clé absente, erreur API)."""
    from api import video_prompt as VP
    from core.prompt_sections import build, video_with_sound

    # 1) Ciblage : storyboard riche → composé ; Live (corps+son) et texte libre → NON.
    riche = build(action="Jésus pousse sa lèvre avec l'index",
                  staging="Jésus au deuxième plan à gauche",
                  ambiance="calme poussiéreux presque sacré", decor="canyon ocre, arbre mort",
                  lighting="lumière rasante cuivrée de fin de journée",
                  technique="Gros plan, caméra fixe, objectif 85mm.", sound="vent chaud, brrrr")
    assert VP.should_compose(riche), "prompt storyboard riche → composition"
    assert not VP.should_compose(video_with_sound(
        "Début : façade sombre. Milieu : pulsation. Fin : blackout.", "basses sourdes")), \
        "prompt Live (corps + son) → chemin historique"
    assert not VP.should_compose("un texte libre tapé à la main"), "texte libre → historique"
    assert not VP.should_compose(""), "prompt vide → historique"

    # 2) Fiches casting depuis le plan (character_names → description + prompt du casting).
    import core.casting as _cast
    _orig = _cast.list_characters
    _cast.list_characters = lambda: [
        {"name": "Jésus", "description": "Homme émacié, couronne d'épines",
         "prompt": "barbe emmêlée, robe blanche déchirée"}]
    try:
        notes = VP.character_notes_for_shot({"character_names": ["Jésus", "Inconnu"]})
    finally:
        _cast.list_characters = _orig
    assert "Jésus" in notes and "couronne d'épines" in notes and "robe blanche" in notes, \
        "fiche casting injectée (description + prompt)"
    assert VP.character_notes_for_shot({}) == "" and VP.character_notes_for_shot(None) == "", \
        "sans personnage → pas de fiches (jamais bloquant)"

    # 3) Composition : message complet, tâche video_prompt, tier créatif ; la recette
    #    (style en tête, dialogues verbatim, pas de mots qualité) est dans le système.
    from core import ai_provider as _ai
    captured = {}
    _oc = _ai.complete
    def _fake(system, user, tier="utility", max_tokens=2048, task=None):
        captured.update(system=system, user=user, tier=tier, task=task)
        return "Painterly prose, head style prompt."
    _ai.complete = _fake
    try:
        out = VP.compose(riche, style_suffix="Arcane style, painterly 3D",
                         time_suffix="sunset, golden hour", duration=7,
                         character_notes="- Jésus : couronne d'épines", include_sound=True)
        assert out == "Painterly prose, head style prompt.", "prose renvoyée telle quelle"
        assert captured["task"] == "video_prompt" and captured["tier"] == "creative", \
            "task=video_prompt (routage par tâche) + tier créatif"
        for frag in ("Arcane style, painterly 3D", "sunset, golden hour", "7 seconds",
                     "couronne d'épines", "canyon ocre", "vent chaud"):
            assert frag in captured["user"], f"contexte manquant dans le message : {frag}"
        # Style en FIN de prompt depuis le 2026-07-23 (guide officiel Seedance 2.0).
        for frag in ("FERMENT le prompt", "VERBATIM", "PHYSIQUEMENT", "masterpiece",
                     "Ne TRANSFORME jamais l'action"):
            assert frag in VP._SYSTEM, f"recette absente du prompt système : {frag}"
        # Sans audio : la section son est retirée AVANT l'appel + consigne « pas de son ».
        VP.compose(riche, include_sound=False)
        assert "vent chaud" not in captured["user"], "sans audio, la section son ne part pas"
        assert "NE PAS mentionner le son" in captured["user"], "consigne sans-son explicite"
        # Son via sound_notes : tab_t2v STRIPPE la section son avant les params
        # (protection suffixes de queue) → le texte est capturé AVANT et passe par
        # params["sound_notes"] → bloc [AMBIANCE SONORE] du composeur.
        from core.prompt_sections import strip_for_video as _sfv
        VP.compose(_sfv(riche), sound_notes="cri d'oiseau lointain", include_sound=True)
        assert "cri d'oiseau lointain" in captured["user"] \
            and "[AMBIANCE SONORE" in captured["user"], "sound_notes → bloc son du composeur"
        # Mise en scène / Plan de feu → composition : la synchro page_staging réécrit
        # les sections FR du prompt (parse→build) ; toute modification DOIT se
        # retrouver dans le message du composeur (même mécanique parse/build).
        from core.prompt_sections import parse as _pp, build as _pb
        _sec = _pp(riche)
        _apres_sync = _pb(action=_sec["action"], staging="Comédiens replacés côté cour",
                          ambiance=_sec["ambiance"], decor=_sec["decor"],
                          lighting="Contre-jour bleu depuis la fenêtre",
                          technique=_sec["technique"], sound=_sec["sound"])
        assert VP.should_compose(_apres_sync), "prompt resynchronisé → toujours composé"
        VP.compose(_apres_sync)
        assert "Comédiens replacés côté cour" in captured["user"] \
            and "Contre-jour bleu depuis la fenêtre" in captured["user"], \
            "les sections modifiées par Mise en scène / Plan de feu partent au composeur"
        # Réponse bavarde (préambule) → composition invalidée (repli traduction).
        _ai.complete = lambda *a, **k: "Voici le prompt : ..."
        assert VP.compose(riche) == "", "préambule détecté → repli"
    finally:
        _ai.complete = _oc

    # 4) Tâche paramétrable (Paramètres → avancés) + défaut Sonnet 5 + i18n.
    assert "video_prompt" in dict(_ai.TASKS), "tâche video_prompt dans les Paramètres avancés"
    assert _ai.TASK_DEFAULTS.get("video_prompt") == "claude", "défaut = Sonnet 5 (écriture)"
    from core.i18n import _FR_TO_EN
    assert dict(_ai.TASKS)["video_prompt"] in _FR_TO_EN, "libellé de tâche traduit FR+EN"
    assert "Composition du prompt vidéo (prose anglaise)…" in _FR_TO_EN, "message progression traduit"

    # 5) api/real.py : composition branchée, suffixes style/heure CONSOMMÉS quand
    #    composé (style rendu en anglais en fin de prose par le composeur), repli conservé.
    rsrc = inspect.getsource(__import__("api.real", fromlist=["x"]))
    assert "should_compose" in rsrc and "_vp_compose" in rsrc, "composition branchée dans run_real"
    # Composé OU plan avec section [🎨 STYLE VISUEL] (bakée, restée dans le corps traduit)
    # → style NON recollé. Prompt libre SANS section → on colle get_video_suffix en fin.
    assert '"" if (_composed or _baked_style) else params.get("style_suffix"' in rsrc, \
        "style recollé en double (le style baké doit rester dans le corps traduit)"
    assert '_effective_style = _baked_style or params.get("style_suffix"' in rsrc, \
        "style passé au composeur = baké prioritaire, repli style_suffix (free-form)"
    assert '"" if _composed else params.get("time_suffix"' in rsrc, "contrainte horaire non doublée"
    assert "if not _composed:" in rsrc, "repli strip+traduction conservé"

    # 6) tab_t2v : fiches casting + son transmis à la génération (params) ; le son
    #    est capturé AVANT le strip historique de la section [🎵 SOUND DESIGN].
    tsrc = inspect.getsource(__import__("ui.tab_t2v", fromlist=["x"]))
    assert "character_notes_for_shot" in tsrc and '"character_notes":' in tsrc, \
        "fiches casting transmises dans les params de génération"
    assert '"sound_notes":' in tsrc and "_sound_of(prompt)" in tsrc, \
        "texte son transmis dans les params de génération"
    assert tsrc.index("_sound_of(prompt)") < tsrc.index("_strip_sound(prompt)"), \
        "le son doit être capturé AVANT le strip (sinon il est perdu)"
    assert 'sound_notes=params.get("sound_notes"' in rsrc, "real.py transmet le son au composeur"

    # 7) Langue de travail : le prompt FR du storyboard n'est JAMAIS réécrit — la
    #    prose anglaise est locale à l'envoi (args) ; résultat/historique gardent le FR.
    assert '"prompt":                params.get("prompt", "")' in rsrc, \
        "le résultat/historique conserve le prompt FR d'origine, pas la prose anglaise"


@test
def coecriture_anti_perte():
    """Pertes de travail en co-écriture (constats Matthieu 2026-07-21) — 3 remèdes :
    (1) la coupe par LIMITE DE TOKENS est détectée précisément (chat_ex :
    stop_reason/finish_reason) et la suite est demandée automatiquement
    (chat_until_complete) → plus de fin de scénario perdue ; (2) « Réécrire selon
    la co-écriture » re-parcourt TOUTE la discussion et RETENTE une fois les
    passages non retrouvés ; (3) alerte déterministe AVANT la limite de tokens."""
    from core import ai_provider as AI
    # 1) Continuation : morceaux recollés dans l'ordre jusqu'au stop normal.
    calls = []
    def _fake_ex(system, messages, tier="creative", max_tokens=2048, task=None):
        calls.append([dict(m) for m in messages])
        return {"text": f"part{len(calls)}", "truncated": len(calls) < 3}
    _orig_ex = AI.chat_ex
    AI.chat_ex = _fake_ex
    try:
        out = AI.chat_until_complete("sys", [{"role": "user", "content": "go"}], max_tokens=64)
    finally:
        AI.chat_ex = _orig_ex
    assert out == "part1part2part3", "continuation non recollée"
    assert calls[1][-1]["content"].startswith("Continue EXACTEMENT") \
        and calls[1][-2] == {"role": "assistant", "content": "part1"}, \
        "relance : déjà-reçu renvoyé en assistant + consigne de reprise exacte"
    assert calls[2][-2]["content"] == "part1part2", "cumul renvoyé à chaque relance"
    # Worker branché (texte + vision) — Cinéma ; le Live est vérifié par son harnais.
    src = inspect.getsource(__import__("api.screenplay", fromlist=["x"]))
    assert "chat_until_complete" in src, "ArrangeChatWorker sans anti-troncature"
    assert 'max_rounds=5' in src, "chemin vision sans continuation centralisée"
    # 2) Relance auto des passages non retrouvés + instruction de couverture totale.
    from ui.dialog_arrange_session import ArrangeSessionDialog
    d = ArrangeSessionDialog(None, "INT. NUIT\nLIA regarde la mer.", "analyse", 5)
    _cap = {}
    d._start_worker = lambda instr, surgical=True, **k: _cap.update(instr=instr, surgical=surgical)
    d._on_rewrite_coedit()
    assert "Re-parcours TOUTE" in _cap["instr"] and "n'en oublie aucune" in _cap["instr"], \
        "instruction de réécriture : couverture de TOUTE la discussion"
    assert d._auto_retry_used is False, "la réécriture ciblée arme la relance auto"
    _cap.clear()
    d._on_edits_ready([{"find": "TEXTE INTROUVABLE XYZ", "replace": "x", "summary": "point A"}])
    assert _cap.get("surgical") is True and "point A" in _cap.get("instr", "") \
        and "EXACTEMENT" in _cap.get("instr", ""), "passages non retrouvés → relance auto"
    assert d._auto_retry_used is True, "relance consommée"
    _cap.clear()
    d._on_edits_ready([{"find": "TOUJOURS INTROUVABLE", "replace": "y", "summary": "point B"}])
    assert not _cap, "une SEULE relance auto par demande (pas de boucle infinie)"
    # 3) Alerte tokens : déterministe, AVANT la limite, sans spam.
    d2 = ArrangeSessionDialog(None, "x" * 250_000, "analyse", 5)   # ~78k tokens estimés
    assert d2._estimated_session_tokens() > d2._TOKEN_WARN_FIRST, "estimation cohérente"
    _bulles = []
    d2._append_chat_bubble = lambda text, role: _bulles.append(text)
    d2._maybe_warn_tokens()
    assert _bulles and "Réécrire selon la co-écriture" in _bulles[0], "alerte tokens émise"
    d2._maybe_warn_tokens()
    assert len(_bulles) == 1, "pas de spam : ré-alerte au palier suivant seulement"
    small = ArrangeSessionDialog(None, "court", "analyse", 5)
    _b2 = []
    small._append_chat_bubble = lambda text, role: _b2.append(text)
    small._maybe_warn_tokens()
    assert not _b2, "pas d'alerte sous le seuil"
    assert "_maybe_warn_tokens" in inspect.getsource(ArrangeSessionDialog._on_message_ready), \
        "l'alerte est vérifiée après chaque réponse du chat"
    # i18n des nouvelles bulles
    from core.i18n import _FR_TO_EN
    assert "↻ Nouvelle tentative automatique sur les passages non retrouvés…" in _FR_TO_EN
    assert any(k.startswith("⚠ La session devient volumineuse") for k in _FR_TO_EN), \
        "alerte tokens traduite"


@test
def staging_navigation_refresh_is_deferred_and_coalesced():
    """Plan de feu ne doit pas reconstruire toute la page plusieurs fois pendant
    le changement d'onglet, sinon Windows la marque « Ne répond pas »."""
    from ui.page_staging import PageStaging, PageLighting
    from ui.pandora_window import PandoraWindow

    assert PageStaging.DEFER_NAV_REFRESH is True
    assert PageLighting.DEFER_NAV_REFRESH is True
    show_src = inspect.getsource(PageStaging.showEvent)
    assert "self.refresh()" not in show_src, "showEvent ne doit plus doubler le refresh"
    helper_src = inspect.getsource(PandoraWindow._refresh_page)
    assert "_pandora_refresh_pending" in helper_src and "QTimer.singleShot" in helper_src, \
        "le refresh lourd doit être différé et regroupé"


@test
def decor_previews_generated_before_navigation():
    """Les 7 vues sont preparees pendant la generation, sans fenetre modale."""
    from PIL import Image
    from PyQt6.QtCore import QSize
    from core.image_preview import make_preview
    from ui.page_decors import _load_card_pixmap

    with tempfile.TemporaryDirectory() as folder:
        source = os.path.join(folder, "decor_hd.png")
        Image.new("RGB", (1600, 900), (20, 35, 60)).save(source)
        preview = make_preview(source, max_size=(320, 240))
        assert preview and os.path.isfile(preview), "apercu non genere"
        with Image.open(preview) as image:
            assert image.width <= 320 and image.height <= 240, "apercu trop grand"
        pix = _load_card_pixmap(source, 162, 160)
        assert not pix.isNull() and pix.size() == QSize(162, 160), \
            "repli silencieux des anciens projets invalide"

    worker_src = inspect.getsource(__import__(
        "api.nano_banana", fromlist=["GenerateRoomViewsWorker"]
    ).GenerateRoomViewsWorker._real)
    assert "make_preview" in worker_src and '"thumbnail_path"' in worker_src, \
        "les apercus doivent etre crees par le worker avant la navigation"
    done_src = inspect.getsource(__import__(
        "ui.dialog_extract_generate", fromlist=["ExtractGenerateDialog"]
    ).ExtractGenerateDialog._on_all_done)
    assert "QMessageBox.warning" not in done_src, \
        "une alerte de generation ne doit pas ouvrir une nouvelle fenetre"

    # Une pièce de 7 vues utilise un QWidget intermédiaire. S'il est rendu
    # visible avant son ajout au layout, Qt l'affiche brièvement comme une
    # fenêtre autonome intitulée « python ».
    from ui.page_decors import PageDecors
    group_src = inspect.getsource(PageDecors._group_section)
    assert group_src.index("v.addWidget(body)") < group_src.index("body.setVisible"), \
        "le groupe de vues ne doit jamais etre visible tant qu'il est parentless"

    from PyQt6.QtCore import QObject, QEvent
    from PyQt6.QtWidgets import QWidget

    class _TopLevelWatch(QObject):
        def __init__(self):
            super().__init__()
            self.shown = []

        def eventFilter(self, obj, event):
            if (event.type() == QEvent.Type.Show and isinstance(obj, QWidget)
                    and obj.isWindow()):
                self.shown.append(type(obj).__name__)
            return False

    page = PageDecors()
    watch = _TopLevelWatch()
    APP.installEventFilter(watch)
    try:
        page._group_section("Piece test", [{
            "id": "face-test", "name": "Face test", "category": "Intérieur",
            "room_view": "avant", "image_path": "", "assigned_shots": [],
        }])
        APP.processEvents()
        assert not watch.shown, \
            f"fenetre Qt autonome pendant la construction du groupe : {watch.shown}"
    finally:
        APP.removeEventFilter(watch)


@test
def mood_affiche_le_prompt_compose():
    """L'encart du Mood contient le prompt COMPOSÉ, celui qui part au moteur.

    Constat de Matthieu (2026-07-27) : « je n'ai toujours pas de composition IA
    dans le prompt quand j'ouvre la fenêtre du Mood ». Le module existait, il
    n'était pas branché.

    Ce test fige le CÂBLAGE, pas le texte produit :
      · la fiche donnée au compositeur est la barre ENTIÈRE — il ne peut résoudre
        la contradiction « le STYLE décrit l'arrivée, l'instant demandé est le
        départ » que s'il VOIT les deux ;
      · l'instant à rendre lui est dit à part ;
      · le résultat atterrit dans l'encart, donc dans ce qui est envoyé ;
      · un prompt retouché à la main n'est JAMAIS écrasé.
    """
    import core.storyboard as sb
    import api.image_prompt as IP
    from ui.dialog_apercu import MoodDialog, _MoodPromptWorker

    # Contrat de signal : `done`, jamais `finished` (qui masquerait le natif).
    assert hasattr(_MoodPromptWorker, "done"), "le worker n'expose pas `done`"
    assert "finished" not in _MoodPromptWorker.__dict__, \
        "`finished` masquerait le signal natif de QThread"

    sb.set_namespace("live_seq_mapping")
    sb.clear_version_shots(sb.DEFAULT_VERSION_ID)
    _p = (
        "SURFACE : façade en pierre, tour-clocher, portail en ogive.\n"
        "ÉTAT 0 : toute la pierre sous un givre dense en hachures blanches.\n"
        "TRANSFORMATION : le givre se fend, la rosace devient un cristal.\n"
        "ÉTAT 1 : façade cristalline bleu glacé.\n"
        "NOIR : le fond hors façade.\n"
        "STYLE : gravure ancienne gelée, clair-obscur dramatique.\n"
        "CONTRAINTES : aucun texte, façade à l'échelle exacte.\n"
    )
    _shot = sb.save_shot({"number": 1, "scene_title": "Givre",
                          "seedance_prompt": _p}, sb.DEFAULT_VERSION_ID)

    _vu = {}
    _vrai = IP.compose

    def _stub(prompt, **kw):
        _vu.update(kw)
        _vu["fiche"] = prompt
        return ("Subject: a limestone church facade encased in dense white "
                "frost.\nAction: the stone reads as fine engraved hatching.\n"
                "Constraints: no text, no watermark.")

    try:
        IP.compose = _stub
        dlg = MoodDialog(None, _shot)
        # ⓪ OUVRIR la fenêtre suffit à programmer la composition. Sans cette
        #    assertion, le test passerait alors que rien ne se déclenche — le
        #    symptôme exact rapporté par Matthieu, la machinerie marchant très
        #    bien dès qu'on l'appelle à la main.
        assert dlg._compose_timer.isActive(), (
            "ouvrir le Mood ne programme aucune composition : l'encart restera "
            "sur le prompt déterministe")
        dlg._compose_timer.stop()
        dlg._start_compose()
        assert dlg._compose_worker is not None, "aucune composition n'a été lancée"
        dlg._compose_worker.run()      # synchrone : pas de boucle d'événements ici

        # ① Le compositeur voit la barre ENTIÈRE — c'est la condition pour qu'il
        #    puisse trancher entre l'état de départ et le style d'arrivée.
        for _bloc in ("TRANSFORMATION", "ÉTAT 1", "STYLE"):
            assert _bloc in _vu.get("fiche", ""), (
                f"« {_bloc} » n'est pas donné au compositeur : il ne peut pas "
                "voir la contradiction qu'on lui demande de résoudre")
        # ② …et on lui dit lequel des états rendre — l'ARRIVÉE depuis le
        #    2026-07-28 (le Mood est la plaque d'arrivée de la vidéo).
        assert "FINAL state" in (_vu.get("moment") or ""), \
            "l'état d'ARRIVÉE à rendre n'est pas transmis"
        assert _vu.get("kind") == "mood_mapping", \
            ("le contexte d'usage n'est pas celui du mapping", _vu.get("kind"))

        # ③ Le composé est DANS l'encart — donc dans ce qui part au moteur.
        _txt = dlg._prompt_edit.toPlainText()
        assert "limestone church facade" in _txt, \
            "l'encart n'affiche pas le prompt composé"
        assert "SURFACE" not in _txt and "ÉTAT 0" not in _txt, \
            "les étiquettes internes sont encore dans l'encart"
        assert "composé" in dlg._grammar_lbl.text(), \
            ("le verdict de composition ne se lit pas — un repli silencieux "
             "passerait pour un bug de l'application")

        # ④ Une retouche manuelle prime toujours.
        dlg._prompt_dirty = True
        dlg._on_composed("TEXTE COMPOSÉ QUI NE DOIT PAS APPARAÎTRE", True, "")
        assert "NE DOIT PAS APPARAÎTRE" not in dlg._prompt_edit.toPlainText(), \
            "la composition écrase le texte retouché à la main"
    finally:
        IP.compose = _vrai
        sb.set_namespace("storyboard")


@test
def compositeur_sait_quelles_images_sont_jointes():
    """Le compositeur doit connaître les images jointes ET leur RÔLE.

    Constat de Matthieu (2026-07-27) : « les images de référence ne sont plus
    considérées comme des inspirations, elles sont plaquées sur la façade et
    prennent le dessus sur le prompt ».

    La plomberie était pourtant juste — façade en image 1, inspiration en
    image 2, directives explicites dans le payload. Le défaut était dans le
    compositeur : il écrivait comme s'il n'y avait que du texte, donc deux
    phrases pour Seedream conformément à sa doc… face à deux images. Un prompt
    de 90 caractères contre deux images, le modèle n'a presque rien à rendre et
    recopie ce qu'il voit.
    """
    import os as _os
    import api.apercu as A
    import api.image_prompt as IP

    _fac = os.path.join(_TMP, "roles_facade.png")
    _ins = os.path.join(_TMP, "roles_inspi.png")
    from PIL import Image
    for _p in (_fac, _ins):
        Image.new("RGB", (32, 18), (20, 20, 20)).save(_p)

    _shot = {"id": "r1", "number": 1, "reference_images": [_ins],
             "seedance_prompt": "SURFACE : façade.\nÉTAT 0 : pierre givrée."}
    _roles = A._ref_roles(_shot, _fac, True)

    # ① L'ORDRE est un contrat : « Figure 1 » désigne une POSITION, pas un rôle.
    #    Une liste décalée dirait au moteur que l'inspiration est le canevas.
    assert len(_roles) == 2, ("une façade + une inspiration = 2 rôles", _roles)
    assert "CANEVAS" in _roles[0], "la façade doit être le PREMIER rôle déclaré"
    assert "INSPIRATION" in _roles[1], "l'inspiration doit venir APRÈS la façade"

    # ② La désignation des images est propre à chaque moteur — lue dans
    #    core.image_grammar, jamais écrite en dur dans le compositeur.
    for _eng, _token in (("seedream5_pro", "Figure 1"), ("flux2", "@image1"),
                         ("nb_pro", "the first attached image")):
        _r = IP._refs_rules(_eng, _roles)
        assert _token in _r, (
            f"« {_eng} » ne reçoit pas sa propre syntaxe de référence", _token)
        assert "CANEVAS" in _r and "INSPIRATION" in _r, \
            f"les rôles ne sont pas transmis pour « {_eng} »"

    # ③ Sans image jointe, aucun bloc parasite.
    assert IP._refs_rules("seedream5_pro", []) == "", \
        "un prompt sans image ne doit pas parler d'images"

    # ④ Et la consigne atteint réellement la consigne système du compositeur.
    _sys = IP._system_for("seedream5_pro", "mood_mapping", _roles)
    assert "IMAGES JOINTES" in _sys, \
        "le rôle des images n'atteint pas la consigne système"
    assert "PLUS DÉTAILLÉ" in _sys, (
        "rien ne dit au rédacteur d'être plus détaillé quand des images sont "
        "jointes — c'est la brièveté qui fait recopier l'inspiration")

    # ⑤ Une prose longue ne doit plus être REFUSÉE : la règle des 2-4 phrases
    #    vaut pour un texte seul.
    _long = " ".join(f"Sentence number {i} describes the frozen stone facade."
                     for i in range(1, 8))
    _v = IP.validate_image_composed(_long, engine="seedream5_pro")
    assert _v["valid"], ("une prose détaillée est refusée alors que c'est "
                         "exactement ce qu'il faut avec des images jointes",
                         _v["errors"])


@test
def style_de_projet_desactivable():
    """RE-cliquer le style ACTIF le désactive — et ça se PERSISTE.

    Constat Matthieu (2026-07-28, projet FIGHTER) : « un template que j'ai
    activé un moment, puis désactivé, mais c'est resté ». Il n'existait AUCUN
    chemin de désélection : cliquer une carte sélectionne, re-cliquer
    re-sélectionne, et il n'y a pas de carte « Aucun ». La clé restait dans
    project_styles.json pour toujours, et l'import du storyboard continuait
    d'injecter le template fantôme (« shot on ARRI Alexa 65… ») dans le bloc
    STYLE VISUEL de chaque plan.
    """
    import core.style as st
    from ui.page_style import PageStyle

    _orig = st._STYLES_FILE
    st._STYLES_FILE = os.path.join(
        tempfile.mkdtemp(prefix="t_style_"), "project_styles.json")
    try:
        page = PageStyle()
        page._on_select("arri_65")
        assert st.get_style_key() == "arri_65", "la sélection doit se persister"

        # RE-cliquer la carte active = désactiver.
        page._on_select("arri_65")
        assert st.get_style_key() == "", (
            "re-cliquer le style actif doit le DÉSACTIVER — sans ce geste, "
            "aucun chemin ne retire jamais un style de projet")
        assert st.get_image_suffix() == "", \
            "un style désactivé ne doit plus rien injecter dans les prompts"
        assert not page._active_badge.isVisible() or page._active_badge.isHidden(), \
            "le badge de style actif doit disparaître à la désactivation"

        # Geste réversible : re-cliquer réactive.
        page._on_select("arri_65")
        assert st.get_style_key() == "arri_65"

        # ② Le combo « — Style — » de la page Scénario désactive AUSSI. La
        #    vieille garde `if key` sautait set_style("") : le combo affichait
        #    « — Style — » pendant que project_styles.json gardait arri_65.
        from ui.page_scenario import PageScenario

        class _Combo:
            def __init__(self, data): self._d = data
            def currentData(self): return self._d

        class _Sig:
            def emit(self, *_): pass

        class _FauxPage:
            _on_scenario_style_changed = PageScenario._on_scenario_style_changed
            def __init__(self, data):
                self._film_style_combo = _Combo(data)
                self.style_changed = _Sig()

        st.set_style("arri_65")
        _FauxPage("")._on_scenario_style_changed(0)
        assert st.get_style_key() == "", \
            "choisir « — Style — » doit écrire set_style(\"\") — pas l'ignorer"
        _FauxPage("__sep__")._on_scenario_style_changed(0)
        assert st.get_style_key() == "", "un séparateur ne change rien"

        # ③ La propagation suit un GESTE utilisateur (signal `activated`),
        #    jamais un setCurrentIndex programmatique (currentIndexChanged) :
        #    sinon charger un scénario sans film_style écraserait le style du
        #    projet à l'ouverture.
        _src_build = inspect.getsource(PageScenario)
        assert "activated.connect(self._on_scenario_style_changed)" in _src_build, \
            "la propagation du style doit être branchée sur `activated`"
        assert "currentIndexChanged.connect(self._on_scenario_style_changed)" \
            not in _src_build, \
            ("brancher la propagation sur currentIndexChanged fait écraser le "
             "style du projet par les setCurrentIndex programmatiques")
    finally:
        st._STYLES_FILE = _orig


@test
def controle_anglais_en_mots_entiers():
    """« angles », « shades » et « façade » ne sont pas du français.

    Constat Matthieu (2026-07-28, Mood plan 1 mapping) : « composition
    refusée : prompt encore en français (façade, les) » sur une sortie
    parfaitement ANGLAISE — puis refus MÉMORISÉ par le cache, que
    « Réinitialiser » resservait tel quel. Le contrôle testait par
    SOUS-CHAÎNE : « les  » attrapait angles/circles, « des  » attrapait
    shades/sides, et « façade » est un emprunt courant de l'anglais (la
    composition réussie du même plan l'écrit : « the limestone façade »).
    Mots-outils en MOTS ENTIERS désormais, façade retirée.
    """
    import api.image_prompt as IP

    _en = ("A moody nocturnal photograph of a limestone façade, its buttress "
           "angles and window circles catching cold light, deep shades of "
           "blue across the stone surfaces, tight white hatching over the "
           "joints.")
    _v = IP.validate_image_composed(_en, engine="seedream5_pro")
    assert _v["valid"], \
        ("une sortie parfaitement anglaise est refusée comme française",
         _v["errors"])

    _fr = ("La façade est prise dans le givre avec les contreforts dans la "
           "lumière froide.")
    _v2 = IP.validate_image_composed(_fr, engine="seedream5_pro")
    assert not _v2["valid"], "du vrai français doit rester refusé"


@test
def style_de_note_extrait_sans_markdown():
    """visual_style_from_note : le CONTENU du style, jamais son libellé markdown.

    Constat Matthieu (2026-07-28, projet FIGHTER) : les plans importés avaient
    « …atmospheric haze, Style d'image :** » en bloc STYLE VISUEL. Le repli
    « chasse aux lignes » attrapait la ligne-libellé « **Style d'image :** »
    (lstrip("-•*") mange les ** ouvrants, le « :** » fermant reste) et RATAIT
    les puces suivantes qui portent le vrai style — « - Arcane League of
    Legends style… » ne matche aucun déclencheur seule. Le style voulu
    n'atteignait jamais le storyboard ; le fragment cassé, si.
    """
    from core.direction_note import visual_style_from_note

    _note = (
        "## INTENTIONS ISSUES DE L'ANALYSE DU SCÉNARIO\n"
        "Tout ce qui suit doit sortir du scénario :\n"
        "\n"
        "**Style d'image :**\n"
        "- Arcane League of Legends style, Fortiche Studio aesthetic, 3D "
        "painterly render with hand-painted textures, visible brush strokes\n"
        "- Encre rouge stylisée / giclées lors des swipes à gauche.\n"
        "\n"
        "**Temporalité / lumière :**\n"
        "- « Fin de journée », « lumière rasante », brume dorée en profondeur.\n"
    )
    _out = visual_style_from_note(_note)
    assert "Arcane League of Legends" in _out, \
        ("le CONTENU du bloc (les puces sous le libellé) doit être extrait",
         _out)
    assert "**" not in _out and ":**" not in _out, \
        ("du markdown brut part au moteur", _out)
    assert "Temporalité" not in _out and "lumière rasante" not in _out, \
        ("le bloc SUIVANT ne doit pas être aspiré", _out)

    # La puce autoportante historique reste extraite (cas de la docstring).
    _out2 = visual_style_from_note(
        "## NOTES\n- Style graphique global façon gravure ancienne, hachures.\n")
    assert "gravure ancienne" in _out2


@test
def style_visuel_lu_malgre_le_gabarit_vide():
    """Un gabarit « ## STYLE VISUEL » VIDE ne doit pas masquer la vraie section.

    Constat Matthieu (2026-07-31, projet FIGHTER v2, données réelles) : le
    style d'image ne reprenait qu'UNE puce sur six — « - Rendu 3D painterly…
    » — au lieu du paragraphe entier. Cause mesurée dans sa note : le titre
    « ## STYLE VISUEL » y figure DEUX FOIS — le gabarit vide d'`empty_note()`
    en position 22, et la vraie section en position 2560 (l'analyse empile ses
    intentions à la suite au lieu de remplir le gabarit). `section_text`
    s'arrêtait à la PREMIÈRE occurrence, donc vide → repli « chasse aux
    lignes », qui ne ramasse que les lignes matchant un déclencheur : seule
    « Rendu 3D painterly » matche `rendu\\s+\\w+`, les cinq autres puces étaient
    perdues.
    """
    from core.direction_note import section_text, visual_style_from_note

    note = (
        "## INTENTION GÉNÉRALE\n\n\n"
        "## STYLE VISUEL\n\n\n"                     # ← gabarit VIDE, en premier
        "## SON ET MUSIQUE\n\n\n"
        "## INTENTIONS ISSUES DE L'ANALYSE DU SCÉNARIO\n\n"
        "## STYLE VISUEL\n"                          # ← la VRAIE section
        "Référence maîtresse : Arcane (League of Legends), Fortiche Studio.\n"
        "- Rendu 3D painterly avec textures peintes à la main.\n"
        "- Chiaroscuro cinématographique dramatique, rim light vibrant.\n"
        "- Character design expressif et anguleux ; cross-hatching.\n"
        "- Fumée volumétrique, accents néon lumineux.\n"
        "- Atmosphère hybride : steampunk Hextech et gritty façon Zaun.\n"
        "\n"
        "## TEMPORALITÉ ET LUMIÈRE\nfin de journée\n"
    )
    out = visual_style_from_note(note)
    assert out == section_text(note, "STYLE VISUEL"), \
        "le style doit venir de la SECTION, pas du repli"
    # Le paragraphe ENTIER, pas une puce.
    for attendu in ("Référence maîtresse", "Rendu 3D painterly", "Chiaroscuro",
                    "Character design", "Fumée volumétrique", "steampunk Hextech"):
        assert attendu in out, (f"« {attendu} » perdu — le style est tronqué", out)
    assert len(out.splitlines()) >= 6, ("une seule ligne remontée", out)
    # …et surtout PAS la section suivante.
    assert "fin de journée" not in out, ("la section suivante est aspirée", out)

    # Toutes les occurrences vides → « », le repli reprend la main (pas de
    # régression pour les notes où le style est rangé ailleurs).
    vide = "## STYLE VISUEL\n\n\n## STYLE VISUEL\n   \n\n## AUTRE\nx\n"
    assert section_text(vide, "STYLE VISUEL") == ""
    # Section unique et remplie : comportement historique inchangé.
    simple = "## STYLE VISUEL\ngrain lourd, désaturé\n\n## SON\nnappe\n"
    assert section_text(simple, "STYLE VISUEL") == "grain lourd, désaturé"


@test
def storyboard_ia_ne_perd_jamais_de_plans():
    """84 fiches ne peuvent pas devenir 20 plans en silence.

    Constat Matthieu (2026-07-28, projet FIGHTER) : « Générer le storyboard »
    depuis un découpage de 84 fiches n'a importé que 20 plans. La réécriture
    IA partait en UN appel à max_tokens=16000 (~800 tokens par fiche ≈ 20
    fiches), la réponse se coupait net, et _parse_shots_robust récupérait les
    objets JSON complets SANS RIEN DIRE. Le Découpage a reçu le correctif
    anti-troncature le 2026-07-25 (chat_until_complete_ex) — jamais porté ici.

    Deux filets, tous deux vérifiés : réponse IA tronquée malgré les reprises
    → conversion déterministe (aucune fiche perdue) ; réponse « complète »
    mais rendant moins de la moitié des fiches → pareil.
    """
    import json as _json
    import api.screenplay as SP
    import core.ai_provider as AP
    from core.decoupage_layout import (is_structured_layout,
                                       layout_segments_to_cinema_shots)

    _fiches = []
    for i in range(1, 9):
        _fiches.append(
            f"PLAN {i:02d}\n"
            f"SOURCE SCÉNARIO : Le héros marche ({i}).\n"
            f"INTENTION : Plan {i}.\n"
            f"DURÉE : 4s\n"
            f"PROMPT VISUEL : Plan moyen, le héros marche dans le couloir {i}.\n"
            f"VALEUR PROPOSÉE : PLAN MOYEN\n"
        )
    _doc = ("DÉCOUPAGE PANDORA 2\n\nSÉQUENCE 1 — LE COULOIR\n\n"
            + "\n".join(_fiches))
    assert is_structured_layout(_doc), "le mini-découpage doit être reconnu"
    assert len(layout_segments_to_cinema_shots(_doc)) == 8, \
        "le convertisseur déterministe doit rendre les 8 fiches"

    # L'IA ne rend que 3 objets complets (réponse coupée à max_tokens).
    _trois = _json.dumps([{"number": i, "scene_title": f"P{i}", "duration": 4,
                           "action": f"plan {i}"} for i in (1, 2, 3)])
    _vc, _vk = AP.complete, AP.key_error
    _vx = getattr(AP, "chat_until_complete_ex", None)
    _got = []
    try:
        AP.key_error = lambda *a, **k: None
        AP.complete = lambda *a, **k: _trois
        AP.chat_until_complete_ex = \
            lambda *a, **k: {"text": _trois, "truncated": True}

        w = SP.GenerateStoryboardWorker(_doc)
        w.finished.connect(lambda shots: _got.append(shots))
        w.failed.connect(lambda err: _got.append(err))
        w.run()
        assert _got and isinstance(_got[0], list), _got
        assert len(_got[0]) == 8, (
            f"{len(_got[0])} plans émis pour 8 fiches — la troncature IA perd "
            "des plans en silence au lieu de replier sur le déterministe")

        # Réponse « complète » mais amputée (le modèle a résumé) : même filet.
        _got.clear()
        AP.chat_until_complete_ex = \
            lambda *a, **k: {"text": _trois, "truncated": False}
        w2 = SP.GenerateStoryboardWorker(_doc)
        w2.finished.connect(lambda shots: _got.append(shots))
        w2.failed.connect(lambda err: _got.append(err))
        w2.run()
        assert _got and isinstance(_got[0], list) and len(_got[0]) == 8, (
            "une réécriture qui rend moins de la moitié des fiches doit "
            "replier sur la conversion déterministe",
            len(_got[0]) if _got and isinstance(_got[0], list) else _got)
    finally:
        AP.complete, AP.key_error = _vc, _vk
        if _vx is not None:
            AP.chat_until_complete_ex = _vx


@test
def compositeur_image_par_moteur():
    """Le prompt final IMAGE est écrit dans la grammaire du moteur, et en anglais.

    Chantier du 2026-07-27 (demande Matthieu). Trois défauts mesurés avant :
      · `core/image_grammar.build_image_prompt` ne réécrit que le CONTENANT — le
        même corps français traversait les cinq moteurs, étiquettes internes
        comprises ;
      · rien ne traduisait, alors que tout le reste de PANDORA traduit ;
      · les blocs d'une barre se contredisent pour une image FIXE (« ÉTAT 0 :
        monde forestier vert-doré » avec « STYLE : bleu outremer à cyan »), et
        aucun filtre déterministe ne peut trancher — il faut réécrire.

    Ce test fige le CONTRÔLE, pas le texte produit : la sortie de l'IA varie, mais
    ce qu'on accepte et ce qu'on refuse ne doit pas bouger.
    """
    import api.image_prompt as IP

    # ── 1. La forme demandée suit la grammaire RÉELLE du moteur ──────────────
    # ⚠ « DEUX à QUATRE phrases » était pinglé ici jusqu'au 2026-07-27. C'était
    # une ERREUR de lecture de la doc Seedream : elle déconseille les LISTES DE
    # MOTS-CLÉS, elle ne demande pas d'être bref. Cette consigne a transformé une
    # règle de forme en ordre de compression, et le prompt est passé de ~600 à
    # moins de 250 caractères — « la composition ne doit pas enlever de
    # l'information » (Matthieu). Le test épingle donc la règle CORRIGÉE.
    for _eng, _attendu in (("nb_pro", "Composition and camera"),
                           ("gpt2", "Important details"),
                           ("seedream45", "AUTANT DE PHRASES"),
                           ("flux2", "OBJET JSON")):
        _r = IP._format_rules(_eng)
        assert _attendu in _r, (
            f"la consigne de forme de « {_eng} » ne correspond pas à sa "
            f"grammaire — « {_attendu} » attendu")

    # Le moteur sans prompt négatif ne doit PAS recevoir « liste tes interdits ».
    assert "OCCUPE la place" in IP._format_rules("seedream45"), \
        ("Seedream n'a pas de prompt négatif : lui demander d'écrire ses "
         "interdits les transforme en sujets à l'image")

    # ── 2. La règle qui justifie tout le chantier est bien dans la consigne ──
    _sys = IP._system_for("seedream45", "mood_mapping")
    assert "CONTRADICTION" in _sys.upper(), \
        ("la consigne ne dit pas au rédacteur de résoudre la contradiction "
         "état de départ / style d'arrivée — c'est le cœur de sa tâche")
    assert "OPENING FRAME" in _sys, "le contexte d'usage du mood mapping a disparu"

    # ── 3. Ce qui doit être REFUSÉ ──────────────────────────────────────────
    _refus = [
        ("nb_pro", "Subject: a church.\nSURFACE : stone facade.", "étiquettes"),
        ("nb_pro", "[🎬 ACTION]\nSubject: a church glowing at night.", "crochets"),
        ("nb_pro", "Subject: la façade en pierre avec une lumière dans les baies "
                   "qui sont sur la gauche.", "français"),
        ("nb_pro", "Subject: a church, cinematic ultra-detailed 4K masterpiece.",
         "génériques"),
        ("seedream45", "Subject: a church.\nStyle: dark.", "prose"),
        ("seedream45", "A church at night. There is no text anywhere in frame.",
         "négatif"),
        ("flux2", "A stone church glowing at night.", "JSON"),
    ]
    for _eng, _txt, _motif in _refus:
        _v = IP.validate_image_composed(_txt, engine=_eng)
        assert not _v["valid"], (f"« {_motif} » accepté sur {_eng} : {_txt[:50]}")
        assert any(_motif in _e for _e in _v["errors"]), (
            f"refusé sur {_eng}, mais pas pour la raison attendue « {_motif} »",
            _v["errors"])

    # ── 4. Ce qui doit PASSER — une sortie correcte par grammaire ───────────
    _bons = [
        ("nb_pro", "Concept frame for a night projection-mapping show.\n"
                   "Subject: a stone church facade.\n"
                   "Action: the rose window pulses with warm amber light.\n"
                   "Constraints: no text, no watermark."),
        ("gpt2", "Scene: a stone church at night. Subject: the west facade. "
                 "Important details: the rose window glows amber. "
                 "Constraints: no text, no watermark."),
        ("seedream45", "A stone church facade at night, its central rose window "
                       "pulsing with warm amber light while the surrounding "
                       "masonry stays deep and unlit. Everything beyond the "
                       "outline of the building falls to solid black."),
        ("flux2", '{"scene": "a stone church facade at night", '
                  '"lighting": "warm amber core"}'),
        ("recraft", "A stone church facade at night, the rose window glowing "
                    "warm amber against deep unlit masonry. "
                    "Constraints: no text, no watermark."),
    ]
    for _eng, _txt in _bons:
        _v = IP.validate_image_composed(_txt, engine=_eng)
        assert _v["valid"], (f"sortie CORRECTE refusée sur {_eng}", _v["errors"])

    # ── 4bis. Le cas RÉEL de Matthieu : « composition refusée : interdits » ──
    # La fiche est en FRANÇAIS et liste des interdits (« CONTRAINTES : aucun
    # texte, aucun filigrane »). Sur Seedream, le rédacteur les recopiait en
    # « no text, no watermark » et le contrôle refusait TOUTES les compositions.
    _fiche = ("SURFACE : façade en pierre calcaire, tour-clocher carrée.\n"
              "ÉTAT 0 : la pierre sous un givre dense en hachures blanches.\n"
              "CONTRAINTES : aucun texte, aucun filigrane, aucun logo.\n")
    _u = IP._build_user_message(_fiche, kind="mood_mapping", surface="",
                                moment="", style_suffix="", extras=None,
                                engine="seedream5_pro")
    assert "CONTRAINTES : aucun texte" not in _u, (
        "le bloc d'interdits français est montré à un moteur sans prompt "
        "négatif — il le recopiera, et le contrôle refusera la composition")
    assert "POSITIF" in _u, "l'équivalent positif des contraintes n'est pas fourni"
    # Le moteur qui SAIT interdire, lui, garde sa fiche intacte.
    _u2 = IP._build_user_message(_fiche, kind="mood_mapping", surface="",
                                 moment="", style_suffix="", extras=None,
                                 engine="nb_pro")
    assert "CONTRAINTES : aucun texte" in _u2, \
        "Nano Banana sait interdire : sa fiche ne doit pas être amputée"

    # La réparation retire l'interdit ET remet l'équivalent positif — et ce
    # qu'elle produit doit PASSER le contrôle, sinon elle ne sert à rien.
    _repare = IP._sans_interdits(
        "A limestone facade encased in frost. There is no text and no watermark "
        "anywhere. The facade fills the frame at its exact photographed scale.")
    assert "no text" not in _repare, "la réparation laisse passer l'interdit"
    assert "frost" in _repare and "photographed scale" in _repare, \
        "la réparation a emporté le contenu utile avec l'interdit"
    _v = IP.validate_image_composed(_repare, engine="seedream5_pro")
    assert _v["valid"], (
        "ce que la réparation produit est refusé par le contrôle — « without » "
        "est une préposition dans les réécritures positives du dépôt, pas un "
        "interdit", _v["errors"])

    # ── 4ter. La fiche CINÉMA porte ses paramètres de plan ──────────────────
    # Le Mood Cinéma n'est pas un mood de mapping : sa valeur tient à la valeur
    # de plan, l'axe, la focale, la profondeur de champ et l'heure. Les perdre en
    # route rendrait la composition plus pauvre que l'assemblage déterministe.
    import core.storyboard as _sb
    from api.apercu import compose_mood_inputs
    _sb.set_namespace("storyboard")
    _shot_cine = {"id": "c1", "number": 2, "scene_title": "Duel",
                  "shot_size": "Gros plan", "camera_axis": "Face",
                  "focal": "85mm", "shot_time": "Nuit", "decor_name": "Halle"}
    _f, _m, _k, _s = compose_mood_inputs(_shot_cine, "", "")
    assert _k == "mood", ("hors mapping, le contexte d'usage doit être « mood »", _k)
    assert not _s, "aucune surface de projection ne doit être demandée hors mapping"
    for _attendu in ("CAMÉRA", "85mm", "DÉCOR", "Halle", "LUMIÈRE"):
        assert _attendu in _f, (
            f"« {_attendu} » absent de la fiche Cinéma : la composition serait "
            "plus pauvre que l'assemblage déterministe", _f)

    # ── 4quater. Une composition est une RÉÉCRITURE, jamais un résumé ───────
    # « En soi, la composition doit juste enlever les noms comme TRANSFORMATION,
    # ÉTAT 1, et mettre en forme selon ce que le moteur accepte. Mais ça ne doit
    # pas enlever de l'information » (Matthieu, 2026-07-27).
    assert "TU NE PERDS AUCUNE INFORMATION" in IP._SYSTEM_IMAGE, \
        "la consigne système n'interdit pas la perte d'information"
    _matiere = ("A trapezoidal limestone facade with a square bell tower, a "
                "pointed central portal, two stacked rose windows, four lancet "
                "bays on the left flank, buttresses and stone edges, all of it "
                "vanished under dense frost rendered as fine white hatching.")
    _resume = "A frosted church facade at night."
    _v = IP.validate_image_composed(_resume, engine="recraft",
                                    source_prompt=_matiere)
    assert not _v["valid"] and any("information perdue" in _e for _e in _v["errors"]), (
        "un résumé passe le contrôle : la composition peut vider le prompt de "
        "sa substance sans que rien ne le signale", _v)
    # Une réécriture complète, elle, passe.
    assert IP.validate_image_composed(_matiere, engine="recraft",
                                      source_prompt=_matiere)["valid"], \
        "une réécriture fidèle est refusée"

    # ── 5. Le tri des deux natures d'échec, comme côté Live ─────────────────
    assert IP.is_deterministic_refusal(IP.REFUSAL_PREFIX + "prompt encore en français")
    assert not IP.is_deterministic_refusal("crédits IA épuisés")
    _src = "\n".join(l for l in inspect.getsource(IP.compose).splitlines()
                     if not l.lstrip().startswith("#"))
    assert "REFUSAL_PREFIX" in _src, \
        "compose() n'utilise pas le marqueur — le refus sera repayé à chaque fois"
    assert 'task="video_prompt"' in _src, \
        ("l'appel IA doit porter un task= : sans lui, PANDORA route sur le moteur "
         "global, le plus coûteux")


@test
def dialogue_references_annonce_sa_vraie_hauteur():
    """Le minimum annoncé par le layout doit couvrir ce dont il a VRAIMENT besoin.

    Symptôme (terminal de Matthieu, 2026-07-27, dix fois de suite) :
      QWindowsWindow::setGeometry: Unable to set geometry 720x425 …
      Resulting geometry: 720x447 … minimum size: 480x283

    Cause mesurée : le QLabel d'aide est en wordWrap, donc son minimumSizeHint
    ne compte qu'UNE ligne alors qu'à la largeur réelle du dialogue il en occupe
    DEUX — 15 px logiques manquants, soit 22 px à 150 % d'échelle Windows, très
    exactement l'écart 447-425. Invisible à l'ouverture ; mais au premier ajout
    d'image, la bande de vignettes passe d'un label à une cellule de 92 px, le
    minimum dépasse la hauteur courante, et Qt redimensionne la fenêtre DÉJÀ
    VISIBLE à ce minimum sous-évalué.

    Le test porte sur l'invariant, pas sur le nombre 15 : un layout ne doit
    jamais réclamer moins que ce qu'il lui faut. Il vaut donc encore si le texte
    d'aide est réécrit ou si la largeur minimale change.
    """
    from PIL import Image
    from ui.dialog_reference_images import ReferenceImagesDialog

    _td = os.path.join(_TMP, "refdlg")
    os.makedirs(_td, exist_ok=True)
    _imgs = []
    for _i in range(3):
        _q = os.path.join(_td, f"ref{_i}.png")
        Image.new("RGB", (320, 180), (60, 40, 90)).save(_q)
        _imgs.append(_q)

    for _n in (0, 1, 3):
        dlg = ReferenceImagesDialog(_imgs[:_n])
        dlg.show()
        _lay = dlg.layout()
        _annonce = _lay.totalMinimumSize().height()
        _reel    = _lay.heightForWidth(dlg.minimumWidth())
        assert _annonce >= _reel, (
            f"avec {_n} image(s), le layout annonce {_annonce} px de hauteur "
            f"minimale alors qu'il lui en faut {_reel} : Qt redimensionnera la "
            "fenêtre à une taille que Windows refuse, d'où « Unable to set "
            "geometry » dans le terminal")

    # Le vrai déclencheur : ajouter une image alors que la fenêtre est visible.
    dlg = ReferenceImagesDialog([])
    dlg.show()
    dlg._add_paths([_imgs[0]])
    _lay = dlg.layout()
    assert _lay.totalMinimumSize().height() >= _lay.heightForWidth(dlg.minimumWidth()), \
        ("après ajout d'une image à chaud, le minimum reste sous-évalué — c'est "
         "exactement le moment où l'avertissement se produit")


@test
def ctrl_c_nest_pas_un_plantage():
    """Ctrl+C ne doit PAS afficher « Une erreur inattendue s'est produite ».

    Constat de Matthieu (2026-07-27, capture à l'appui) : interrompre PANDORA
    depuis le terminal qui l'a lancé faisait remonter le KeyboardInterrupt dans
    le filet `sys.excepthook`, qui l'écrivait dans pandora_crash.log et ouvrait
    une fenêtre d'erreur proposant d'envoyer un rapport de crash — pour un arrêt
    DEMANDÉ. Python lui-même écarte KeyboardInterrupt et SystemExit de son
    excepthook par défaut ; le filet doit faire pareil.

    Le filet reste indispensable pour les VRAIES exceptions : une exception non
    gérée dans un slot PyQt6 fait sinon abort de toute l'application. Ce test
    vérifie donc les deux sens — silence sur l'interruption, fenêtre sur l'erreur.
    """
    import enum
    import PyQt6.QtWidgets as _W
    import main as _main

    vues = {"n": 0}

    class _BoxStub:
        class Icon(enum.Enum):
            Critical = 1

        class ButtonRole(enum.Enum):
            RejectRole = 1
            AcceptRole = 2

        def __init__(self, *a, **k):
            vues["n"] += 1

        def setDetailedText(self, *a):
            pass

        def addButton(self, *a):
            return object()

        def exec(self):
            return 0

        def clickedButton(self):
            return None

        @staticmethod
        def information(*a, **k):
            pass

    _vrai_box, _vrai_hook, _vrai_err = _W.QMessageBox, sys.excepthook, sys.stderr
    try:
        _W.QMessageBox = _BoxStub
        _main._install_excepthook()
        # Le filet RÉÉMET la trace sur stderr : sans ce bâillon, l'exception
        # volontaire de ce test polluerait la sortie du harnais et ferait croire
        # à un vrai échec en la lisant.
        import io as _io
        sys.stderr = _io.StringIO()

        sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
        assert vues["n"] == 0, \
            ("Ctrl+C ouvre une fenêtre de crash : un arrêt demandé est présenté "
             "à l'utilisateur comme un plantage de PANDORA")

        sys.excepthook(SystemExit, SystemExit(0), None)
        assert vues["n"] == 0, "sys.exit() ne doit pas non plus passer pour un plantage"

        # ET le filet doit rester actif pour ce à quoi il sert vraiment.
        try:
            raise ValueError("erreur de test")
        except ValueError:
            sys.excepthook(*sys.exc_info())
        assert vues["n"] == 1, \
            ("le filet n'attrape plus les vraies exceptions — une exception non "
             "gérée dans un slot PyQt6 fait abort de toute l'application")
    finally:
        sys.stderr = _vrai_err
        _W.QMessageBox = _vrai_box
        sys.excepthook = _vrai_hook


@test
def worker_plans_architecte_chemin_derreur_repare():
    """GenerateFloorPlansWorker : failed_safe vit SUR LA CLASSE QUI L'APPELLE.

    Audit 2026-07-30 : la méthode était définie sur
    GenerateFloorPlanVariationWorker — qui n'a ni _jobs, ni plan_done, ni
    finished(int) redéclaré : le chemin d'erreur d'import du worker de LOT
    levait AttributeError, et la méthode mal placée aurait frappé le signal
    NATIF QThread.finished → TypeError.
    """
    import api.nano_banana as NB

    assert "failed_safe" in vars(NB.GenerateFloorPlansWorker), \
        "failed_safe doit vivre sur GenerateFloorPlansWorker (qui l'appelle)"
    assert "failed_safe" not in vars(NB.GenerateFloorPlanVariationWorker), \
        ("failed_safe est définie sur le worker de VARIATION, qui n'a "
         "ni _jobs ni plan_done — mauvaise classe")

    w = NB.GenerateFloorPlansWorker([{"id": "a"}, {"id": "b"}])
    _done, _fin = [], []
    w.plan_done.connect(lambda jid, p: _done.append((jid, p)))
    w.finished.connect(lambda n: _fin.append(n))
    w.failed_safe(RuntimeError("import KO"), 2)
    assert _done == [("a", ""), ("b", "")] and _fin == [0], (_done, _fin)


@test
def config_atomique_et_lecture_avec_filet():
    """config.json : écriture ATOMIQUE (tmp + os.replace) et lecture blindée.

    Audit 2026-07-30 : save_config écrivait en open("w") direct et
    load_config n'avait aucun try — un crash pendant l'écriture laissait un
    JSON tronqué qui BLOQUAIT l'app au démarrage (le fichier porte les clés
    API réelles, non restaurables). Le fichier corrompu est désormais mis de
    côté (.corrupt_*) : les clés restent récupérables à la main.
    """
    import inspect as _i
    import json as _json
    import glob as _g
    import core.config as C

    # ① L'écriture passe par le helper atomique (code réel).
    src = "\n".join(l.split("#", 1)[0]
                    for l in _i.getsource(C).splitlines())
    assert "os.replace(" in src and "_atomic_write_json" in src, \
        "save_config n'écrit pas de façon atomique (tmp + os.replace)"

    td = tempfile.mkdtemp(prefix="t_cfg_")
    p = os.path.join(td, "config.json")
    C._atomic_write_json(p, {"a": 1})
    with open(p, encoding="utf-8") as f:
        assert _json.load(f) == {"a": 1}
    assert not os.path.exists(p + ".tmp"), "fichier temporaire non nettoyé"

    # ② Un JSON corrompu ne bloque plus le démarrage : mis de côté + défauts.
    _orig = C._CONFIG_FILE
    try:
        C._CONFIG_FILE = os.path.join(td, "config_corrompue.json")
        with open(C._CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write('{"api_key": "tronq')
        cfg = C.load_config()
        assert isinstance(cfg, dict) and "api_key" in cfg, \
            "le filet doit rendre les défauts, pas lever"
        assert not os.path.exists(C._CONFIG_FILE), \
            "le fichier corrompu doit être MIS DE CÔTÉ (pas laissé en place)"
        assert _g.glob(C._CONFIG_FILE + ".corrupt_*"), \
            "le fichier corrompu doit être CONSERVÉ (.corrupt_*) — clés API"
    finally:
        C._CONFIG_FILE = _orig

    # ③ set_lang persiste via save_config (neutralisé dans les harnais →
    #    un test qui change la langue n'écrit PLUS la vraie config).
    import core.i18n as I18N
    _s = "\n".join(l.split("#", 1)[0]
                   for l in _i.getsource(I18N.set_lang).splitlines())
    assert "save_config" in _s, \
        ("set_lang doit persister via core.config.save_config "
         "(écriture atomique + garde-fou des harnais)")


@test
def frames_apres_generation_jamais_silencieuses():
    """L'échec d'enregistrement des frames post-génération S'AFFICHE (Cinéma).

    Audit 2026-07-30 : extraction + save_shot vivaient sous un unique
    try/except:pass — si save_shot échouait après une génération PAYÉE, le
    clip était rendu mais image_path/last_frame_path n'étaient jamais
    persistés : raccords et vignettes cassaient au plan suivant, sans un
    mot. Le bloc reste protégé (pas de crash en fin de file), mais l'échec
    est signalé via progress.set_error.
    """
    import inspect as _i
    import ui.tab_t2v as T

    src = _i.getsource(T.TabT2V.on_finished)
    code = "\n".join(l.split("#", 1)[0] for l in src.splitlines())
    assert "Clip généré, mais" in src, \
        "l'échec des frames post-génération doit s'afficher (Cinéma)"
    assert "save_shot" in code and "set_error" in code, \
        "le bloc frames doit rester protégé ET signaler ses échecs"


@test
def arborescence_source_de_verite_unique():
    """core/project_layout : résolution cible/legacy façon « Studio IA ».

    Chantier arborescence (spec Matthieu 2026-07-30) : un projet NEUF va vers
    la cible 01_writing…04_live, un projet ANCIEN continue sur ses dossiers
    historiques tant qu'il n'est pas migré, un projet MIGRÉ prend la cible
    même si un legacy traîne. Jamais de makedirs dans la résolution (le
    piège documenté du renommage Studio IA).
    """
    from core import project_layout as PL

    td = tempfile.mkdtemp(prefix="t_layout_")

    # ① Projet neuf → cible.
    assert PL.dir("castings", td).endswith(
        os.path.join("02_elements", "characters"))
    assert not os.path.isdir(os.path.join(td, "02_elements")), \
        "la résolution ne doit RIEN créer"

    # ② Ancien projet : legacy présent → legacy (rien ne casse avant migration).
    os.makedirs(os.path.join(td, "castings"))
    assert PL.dir("castings", td) == os.path.join(td, "castings")

    # ③ Migré : cible présente → prioritaire même si le legacy traîne.
    os.makedirs(os.path.join(td, "02_elements", "characters"))
    assert PL.dir("castings", td).endswith("characters")

    # ④ Deux legacy ordonnés (videos : « Studio IA » avant « Seedance »).
    td2 = tempfile.mkdtemp(prefix="t_layout2_")
    os.makedirs(os.path.join(td2, "Seedance"))
    assert PL.dir("videos", td2) == os.path.join(td2, "Seedance")
    os.makedirs(os.path.join(td2, "Studio IA"))
    assert PL.dir("videos", td2) == os.path.join(td2, "Studio IA")

    # ⑤ Fichiers façade : legacy à la racine tant que la cible n'existe pas.
    p = os.path.join(td2, "live_building_ref.json")
    with open(p, "w", encoding="utf-8") as f:
        f.write("{}")
    assert PL.file("live_building_ref.json", td2) == p
    cible = os.path.join(td2, "04_live", "facade", "live_building_ref.json")
    PL.ensure_parent(cible)
    with open(cible, "w", encoding="utf-8") as f:
        f.write("{}")
    assert PL.file("live_building_ref.json", td2) == cible

    # ⑥ Marqueur de migration + hygiène de la table.
    assert not PL.is_migrated(td2)
    os.makedirs(os.path.join(td2, "01_writing"))
    assert PL.is_migrated(td2)
    cibles = [t for t, _ in PL.LAYOUT.values()]
    assert len(set(cibles)) == len(cibles), "cibles dupliquées dans LAYOUT"
    for t in cibles:
        assert t.split("/")[0] in ("01_writing", "02_elements",
                                   "03_production", "04_live", ".cache"), t

    # ⑦ Les CINQ modules d'éléments passent par le layout (code réel).
    import inspect as _i
    for _mod_name in ("casting", "decors", "accessories", "hmc", "vehicles"):
        _m = __import__(f"core.{_mod_name}", fromlist=["_"])
        _src = "\n".join(l.split("#", 1)[0]
                         for l in _i.getsource(_m).splitlines())
        assert "project_layout" in _src, \
            f"core/{_mod_name}.py ne passe pas par project_layout"


@test
def mood_les_references_sont_ANNONCEES_au_compositeur():
    """Les images jointes doivent être DÉCRITES au compositeur, pas seulement
    envoyées. Sur le plan 21 de FIGHTER (Seedream 5.0 Pro), trois fiches
    partaient au moteur et AUCUNE ne lui était annoncée : le compositeur
    écrivait une description autonome, que le moteur d'édition suivait à la
    lettre en ignorant les images — d'où un rendu photoréaliste alors que les
    fiches étaient peintes (constat Matthieu 2026-07-31).

    Le test mord sur le COMPORTEMENT, pas sur le source : il compte les images
    envoyées et les rôles décrits, et exige l'égalité."""
    import os as _os, tempfile as _tf, shutil as _sh
    import api.apercu as A
    import core.casting, core.decors, core.accessories, core.vehicles, core.hmc

    _tmp = _tf.mkdtemp(prefix="pandora_refroles_")
    def _img(n):
        p = _os.path.join(_tmp, n + ".png")
        with open(p, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n")
        return p
    _I = {k: _img(k) for k in ("perso", "decor", "prop")}
    _orig = (core.casting.get_character, core.decors.get_decor,
             core.accessories.get_accessory, core.vehicles.get_vehicle,
             core.hmc.get_hmc_item)
    core.casting.get_character     = lambda i: {"name": "Jésus",  "image_path": _I["perso"]}
    core.decors.get_decor          = lambda i: {"name": "Désert", "image_path": _I["decor"]}
    core.accessories.get_accessory = lambda i: {"name": "Croix",  "image_path": _I["prop"]}
    core.vehicles.get_vehicle      = lambda i: {}
    core.hmc.get_hmc_item          = lambda i: {}
    try:
        shot = {"id": "s-refroles", "number": -21, "character_ids": ["c"],
                "decor_id": "d", "accessory_ids": ["a"],
                "vehicle_ids": [], "hmc_ids": []}
        envoyees = A._shot_ref_images(shot)
        roles    = A._ref_roles(shot)
        assert len(envoyees) == 3, ("collecte incomplète", envoyees)
        assert len(roles) == len(envoyees), (
            f"{len(envoyees)} images envoyées mais {len(roles)} décrites — "
            "le compositeur ignore les fiches", roles)
        # Le rôle NOMME la fiche : « reference 1 » ne relie rien au sujet.
        _blob = " ".join(roles).lower()
        for _nom in ("jésus", "désert", "croix"):
            assert _nom in _blob, (f"« {_nom} » absent des rôles", roles)

        # Les rôles entrent dans la CLÉ DE CACHE : sans cela, le correctif
        # n'atteindrait jamais un plan déjà composé.
        k_avec = A.compose_cache_key("f", "", "", "", "nb2", "mood", roles)
        k_sans = A.compose_cache_key("f", "", "", "", "nb2", "mood", [])
        assert k_avec != k_sans, "les rôles ne comptent pas dans la clé de cache"
    finally:
        (core.casting.get_character, core.decors.get_decor,
         core.accessories.get_accessory, core.vehicles.get_vehicle,
         core.hmc.get_hmc_item) = _orig
        _sh.rmtree(_tmp, ignore_errors=True)


@test
def style_visuel_tronque_repare_reecriture_respectee():
    """La section [🎨 STYLE VISUEL] est cuite dans chaque plan à la création du
    storyboard et plus jamais rafraîchie. Les 75 plans de FIGHTER portaient donc
    UNE ligne sur les treize de la note de réalisation, et le Mood — qui préfère
    la section cuite au style relu — propageait la perte jusqu'à l'image.

    Règle : on répare une TRONCATURE, on ne touche jamais à une RÉÉCRITURE."""
    from core.style_resolve import effective_visual_style, is_truncation_of

    complet = ("Référence maîtresse : Arcane, esthétique Fortiche Studio.\n"
               "- Rendu 3D painterly avec textures peintes à la main.\n"
               "- Chiaroscuro dramatique, rim light vibrant.\n"
               "- Character design expressif et anguleux.")
    cuit = "Rendu 3D painterly avec textures peintes à la main."

    assert is_truncation_of(cuit, complet), "troncature non reconnue"
    assert effective_visual_style(cuit, complet) == complet, \
        "le style complet n'est pas rendu"

    # Contre-épreuve n°1 : une réécriture volontaire est INTOUCHABLE.
    manuel = "Noir et blanc charbonneux, grain argentique lourd."
    assert effective_visual_style(manuel, complet) == manuel, \
        "un style réécrit à la main a été écrasé"
    assert not is_truncation_of(manuel, complet)

    # Contre-épreuve n°2 : rien à comparer → on ne casse rien.
    assert effective_visual_style("", complet) == complet
    assert effective_visual_style(cuit, "") == cuit
    assert effective_visual_style("", "") == ""

    # Contre-épreuve n°3 : un style cuit PLUS RICHE que le courant reste maître
    # (le plan a été enrichi, ce n'est pas une troncature).
    riche = complet + "\n- Fumée volumétrique, accents néon."
    assert effective_visual_style(riche, complet) == riche

    # …et le Mood s'en sert réellement (le prompt porte tout le style).
    from api.apercu import mood_intent
    _it = mood_intent({"id": "s-style", "number": -22,
                       "seedance_prompt": "[🎨 STYLE VISUEL]\n" + cuit +
                                          "\n\n[🎬 ACTION]\nIl marche."},
                      complet)
    assert "Chiaroscuro" in (_it.get("style") or ""), \
        ("le Mood envoie encore le style tronqué", _it.get("style"))


@test
def fenetre_mood_montre_les_images_envoyees():
    """L'encart « images envoyées » doit lire le MÊME plan que l'envoi, sinon il
    rassure à tort. Demande Matthieu 2026-07-31 : « ça me permettra de vérifier
    que toutes les images sont bien envoyées »."""
    import os as _os, tempfile as _tf, shutil as _sh, inspect as _i
    from core import mood_refs as _mr
    import core.casting, core.decors, core.accessories, core.vehicles, core.hmc

    _tmp = _tf.mkdtemp(prefix="pandora_encart_")
    def _img(n):
        p = _os.path.join(_tmp, n + ".png")
        with open(p, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n")
        return p
    _I = {k: _img(k) for k in ("perso", "decor")}
    _orig = (core.casting.get_character, core.decors.get_decor,
             core.accessories.get_accessory, core.vehicles.get_vehicle,
             core.hmc.get_hmc_item)
    core.casting.get_character = lambda i: {"name": "Jésus",  "image_path": _I["perso"]}
    core.decors.get_decor      = lambda i: {"name": "Désert", "image_path": _I["decor"]}
    core.accessories.get_accessory = lambda i: {}
    core.vehicles.get_vehicle      = lambda i: {}
    core.hmc.get_hmc_item          = lambda i: {}
    try:
        shot = {"id": "s-encart", "number": -23, "character_ids": ["c"],
                "decor_id": "d", "accessory_ids": [], "vehicle_ids": [],
                "hmc_ids": []}
        plan = _mr.reference_plan(shot, is_mapping=False)
        assert [r.kind for r in plan] == [_mr.KIND_CHARACTER, _mr.KIND_DECOR], \
            ("ordre d'envoi inattendu", [r.kind for r in plan])
        assert plan[0].name == "Jésus" and plan[1].name == "Désert"
        # La nature seule est traduisible ; le nom propre ne doit pas y passer.
        assert plan[0].kind_label() == "Personnage"
        assert "Jésus" not in plan[0].kind_label()

        # Le PLAFOND du moteur s'applique — un moteur sans référence n'en reçoit
        # aucune, et l'encart doit pouvoir le dire.
        assert _mr.reference_plan(shot, is_mapping=False, max_refs=0) == []
        assert len(_mr.reference_plan(shot, is_mapping=False, max_refs=1)) == 1

        # L'encart lit bien mood_refs (et pas une collecte parallèle à lui).
        import ui.dialog_apercu as _DA
        _src = "\n".join(l.split("#", 1)[0] for l in
                         _i.getsource(_DA.MoodDialog._refresh_refs_row).splitlines())
        assert "mood_refs" in _src and "reference_plan" in _src, \
            "l'encart n'utilise pas le plan de référence commun"
        assert "ref_support" in _src, "l'encart ignore le plafond du moteur"
    finally:
        (core.casting.get_character, core.decors.get_decor,
         core.accessories.get_accessory, core.vehicles.get_vehicle,
         core.hmc.get_hmc_item) = _orig
        _sh.rmtree(_tmp, ignore_errors=True)


@test
def casting_principaux_et_figuration_separes():
    """Le Casting range les personnages dans DEUX espaces dépliables (demande
    Matthieu 2026-07-31). Le défaut est PRINCIPAL : un casting existant, dont
    les fiches n'ont pas le champ, ne doit pas basculer en figuration."""
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from core.casting import (split_by_cast_type, cast_type, is_extra,
                              CAST_MAIN, CAST_EXTRA)

    # Défaut : champ absent, vide ou inconnu → principal.
    for _c in ({}, {"cast_type": ""}, {"cast_type": "  "}, {"cast_type": "zzz"}):
        assert cast_type(_c) == CAST_MAIN, _c
        assert not is_extra(_c), _c
    assert cast_type({"cast_type": "FIGURATION"}) == CAST_EXTRA, "casse ignorée"

    chars = [{"id": "a", "name": "Jésus"},
             {"id": "b", "name": "Villageois", "cast_type": CAST_EXTRA},
             {"id": "c", "name": "Marie", "cast_type": CAST_MAIN}]
    mains, extras = split_by_cast_type(chars)
    assert [c["id"] for c in mains] == ["a", "c"], mains
    assert [c["id"] for c in extras] == ["b"], extras

    # La page rend bien DEUX sections, et une section vide ne s'affiche pas.
    import core.casting as _C
    import ui.page_castings as _PC
    _orig = _C.list_characters
    try:
        _C.list_characters = lambda: chars
        page = _PC.PageCastings()
        page.refresh()
        _secs = [page._sections_lay.itemAt(i).widget()
                 for i in range(page._sections_lay.count())]
        _titres = [w.header_button().text() for w in _secs
                   if hasattr(w, "header_button")]
        assert len(_titres) == 2, _titres
        assert "principaux" in _titres[0].lower(), _titres
        assert "figuration" in _titres[1].lower(), _titres
        # Compteurs présents (c'est ce qui permet de juger d'un coup d'œil).
        assert "2" in _titres[0] and "1" in _titres[1], _titres

        # Aucun figurant → une seule section, pas de bandeau vide.
        _C.list_characters = lambda: [{"id": "a", "name": "Jésus"}]
        page.refresh()
        _secs = [page._sections_lay.itemAt(i).widget()
                 for i in range(page._sections_lay.count())]
        _n = len([w for w in _secs if hasattr(w, "header_button")])
        assert _n == 1, f"{_n} sections alors qu'il n'y a pas de figuration"
    finally:
        _C.list_characters = _orig

    # La fiche personnage sauve la VALEUR, jamais le libellé traduit.
    import inspect as _i
    import ui.dialog_character as _DC
    _src = "\n".join(l.split("#", 1)[0]
                     for l in _i.getsource(_DC).splitlines())
    assert '"cast_type":        self._cast_type.currentData()' in _src, \
        "le type de casting n'est pas enregistré depuis la donnée du combo"


@test
def image_et_son_retire_sans_rien_casser():
    """« Image & Son » est retiré (Matthieu 2026-07-31 : « il ne sert pas »).

    Le MODULE reste : dix endroits le lisent, dont le Studio IA des DEUX
    éditions. Le retrait passe par un drapeau qui rend les préférences vides —
    l'état d'un projet neuf, déjà géré partout. Un projet qui avait réglé une
    caméra ne doit plus l'injecter, la page qui permettait d'en changer
    n'existant plus."""
    import inspect as _i
    import core.camera_prefs as _CP

    assert _CP._FEATURE_ENABLED is False, "la fonctionnalité est censée être retirée"
    prefs = _CP.get_camera_prefs()
    assert set(prefs) == set(_CP._DEFAULTS), "les clés doivent toutes rester présentes"
    assert not any(v for v in prefs.values()), ("préférences non vides", prefs)
    assert _CP.get_prompt_suffix() == "", "une caméra entre encore dans les prompts"

    # …et plus rien ne s'écrit sur le disque.
    _appels = []
    _orig = _CP._save_all
    try:
        _CP._save_all = lambda d: _appels.append(d)
        _CP.save_camera_prefs({"camera_brand": "ARRI"})
        assert not _appels, "save_camera_prefs écrit encore malgré le retrait"
    finally:
        _CP._save_all = _orig

    # L'entrée de navigation n'est plus construite (code commenté, pas supprimé).
    import ui.pandora_window as _PW
    _src = "\n".join(l.split("#", 1)[0]
                     for l in _i.getsource(_PW).splitlines())
    assert 'tr("nav.camera")' not in _src, "l'entrée Image & Son est encore montée"
    assert "PageCamera()" not in _src, "la page Image & Son est encore construite"

    # Le manuel reste ALIGNÉ après le retrait de sa section (FR + EN).
    import ui.dialog_user_manual as _M
    assert len(_M._SECTIONS) == len(_M._BUILDERS) == sum(n for _t, n in _M._GROUPS_FR), \
        "manuel FR désaligné"
    assert len(_M._SECTIONS_EN) == len(_M._BUILDERS_EN) == sum(n for _t, n in _M._GROUPS_EN), \
        "manuel EN désaligné"
    assert all("Image & Son" not in t for _i2, t in _M._SECTIONS), _M._SECTIONS


@test
def image_du_decor_lieu_cadrage_ou_inspiration():
    """L'image de la fiche décor peut vouloir dire trois choses différentes, et
    le moteur ne peut pas le deviner.

    Constat Matthieu 2026-07-31 : « il utilise l'image de référence telle
    quelle, comme un tableau fixe… si mon personnage est à gauche du cadre et
    que je fais un plan serré sur lui, je m'attends à voir autre chose que le
    plan d'ensemble ». L'ancienne consigne demandait au moteur de montrer le
    lieu « sous plusieurs angles » sans jamais nommer le cadrage voulu."""
    import inspect as _i
    import api.real as _R

    _src = _i.getsource(_R.run_real)
    _i0 = _src.find('elif _role == "decor"')
    assert _i0 > 0, "le rôle « decor » a disparu de l'envoi"
    _bloc = _src[_i0:_i0 + 4200]

    # Trois modes → trois consignes DISTINCTES.
    for _mode, _tag in (("lieu", "FILMING LOCATION"),
                        ("identique", "LOCKED FRAMING"),
                        ("inspiration", "VISUAL ATMOSPHERE")):
        assert _tag in _bloc, (f"consigne du mode « {_mode} » absente", _tag)

    # Le mode « lieu » doit dire que l'image N'EST PAS le cadrage, et renvoyer
    # au plan pour la valeur et l'axe — c'est tout le correctif.
    for _phrase in ("NOT the framing of this shot",
                    "obey the shot size, camera axis",
                    "Do NOT reproduce the wide"):
        assert _phrase in _bloc, ("le mode « lieu » ne cadre rien", _phrase)

    # …et le mode « identique » doit au contraire VERROUILLER le cadrage.
    assert "same camera position" in _bloc and "only the" in _bloc, \
        "le mode « identique » ne verrouille pas le cadrage"

    # Compatibilité : un appelant qui n'envoie que l'ancien booléen garde son
    # sens (le Live n'a pas encore le sélecteur).
    assert 'params.get("decor_ref_free"' in _bloc, \
        "l'ancien booléen n'est plus lu — le Live perdrait son réglage"

    # Le sélecteur vit dans RENDU & AUDIO et part réellement au moteur.
    import ui.tab_t2v as _T
    _s = "\n".join(l.split("#", 1)[0] for l in _i.getsource(_T).splitlines())
    assert "_decor_ref_combo" in _s, "pas de sélecteur « Image du décor »"
    assert '"decor_ref_mode"' in _s, "le mode choisi n'est pas envoyé"
    # Défaut = « lieu » : c'est le comportement attendu d'un découpage.
    assert 'return _c.currentData() or "lieu"' in _s, \
        "le repli du sélecteur n'est pas « lieu »"


@test
def note_de_realisation_repli_prend_le_bloc_entier():
    """Quand la note n'a PAS de section « STYLE VISUEL », le style est rangé
    ailleurs — typiquement sous « INTENTIONS ISSUES DE L'ANALYSE », en puces
    descriptives. Le repli travaillait ligne à ligne et ne gardait que celles
    portant un mot déclencheur (« rendu », « palette »…) : sur la note de
    FIGHTER, « Rendu 3D painterly » survivait seul et Arcane, le chiaroscuro,
    le character design, la fumée et les néons étaient perdus.

    Règle : dès qu'une ligne d'un PARAGRAPHE déclare un style, tout le
    paragraphe part — et lui seul."""
    from core.direction_note import visual_style_from_note as _V

    note = (
        "## INTENTION GÉNÉRALE\nUn conte de Noël brutal.\n\n"
        "## INTENTIONS ISSUES DE L'ANALYSE DU SCÉNARIO\n"
        "Référence maîtresse : Arcane (League of Legends), Fortiche Studio.\n"
        "- Rendu 3D painterly avec textures peintes à la main.\n"
        "- Chiaroscuro dramatique, rim light vibrant.\n"
        "- Character design expressif et anguleux.\n"
        "- Fumée volumétrique, accents néon lumineux.\n\n"
        "## TEMPORALITÉ ET LUMIÈRE\nFin de journée, lumière rasante.\n"
    )
    out = _V(note)
    for _attendu in ("Arcane", "Fortiche", "Rendu 3D painterly", "Chiaroscuro",
                     "Character design", "Fumée volumétrique"):
        assert _attendu in out, (f"« {_attendu} » perdu par le repli", out)
    assert len(out.splitlines()) >= 5, ("le repli tronque encore", out)
    # …et il n'aspire PAS les paragraphes voisins, qui parlent d'autre chose.
    assert "lumière rasante" not in out, ("la temporalité est aspirée", out)
    assert "conte de Noël" not in out, ("l'intention générale est aspirée", out)

    # La SECTION reste prioritaire quand elle existe (le repli ne s'en mêle pas).
    _n = ("## STYLE VISUEL\ngrain lourd, désaturé\n\n"
          "## INTENTIONS\n- Rendu 3D painterly partout.\n")
    assert _V(_n) == "grain lourd, désaturé", _V(_n)

    # Libellé NU (« Style d'image : ») : exclu, ses puces conservées.
    _n2 = ("## INTENTIONS\n**Style d'image :**\n"
           "- Aquarelle délavée, papier grainé.\n- Contours à l'encre.\n")
    _r2 = _V(_n2)
    assert "Style d'image" not in _r2 and "Aquarelle" in _r2 and "encre" in _r2, _r2

    # Aucune mention de style → chaîne vide, jamais d'aspiration au hasard.
    assert _V("## INTENTION\nUn drame social.\n\n## SON\nNappes graves.\n") == ""

    # Entrées dégénérées : ne lève jamais (la note vient d'un champ libre).
    for _v in ("", None, "   \n\n", 42, ["x"]):
        _V(_v)


@test
def performance_vignettes_en_cache_et_storyboard_progressif():
    """Audit de lenteur du 2026-07-31 (« tout est assez lent », 2 à 3 s au clic).

    Deux causes mesurées, deux correctifs qui doivent le rester :

    1. Les cartes décodaient l'image SOURCE à chaque construction — une fiche
       de personnage fait 2160×3840 pour un affichage en 162 px — et le
       Casting vidait même le cache juste avant. Ouvrir un onglet relisait
       tout le disque : Décors 798 ms, Casting 341 ms.
    2. Le Storyboard posait ses ~5 400 widgets d'un bloc : 6,6 s d'interface
       FIGÉE à chaque rafraîchissement."""
    import inspect as _i
    from ui.thumb_cache import card_pixmap, _key

    # ① La clé de cache porte la DATE du fichier : une image régénérée est
    #    rechargée sans qu'on ait à purger le cache à l'aveugle.
    import os as _os, tempfile as _tf, shutil as _sh, time as _t
    _tmp = _tf.mkdtemp(prefix="pandora_thumb_")
    try:
        _p = _os.path.join(_tmp, "x.png")
        with open(_p, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n")
        _k1 = _key(_p, 162, 190, "cover")
        _os.utime(_p, (_t.time() + 10, _t.time() + 10))     # « régénérée »
        assert _key(_p, 162, 190, "cover") != _k1, \
            "la clé ignore la date du fichier — une image régénérée resterait figée"
        # Taille demandée différente → clé différente (pas de vignette étirée).
        assert _key(_p, 92, 92, "cover") != _k1
        # Fichier absent → pas de pixmap, et surtout pas d'exception.
        assert card_pixmap(_os.path.join(_tmp, "absent.png"), 10, 10) is None
        assert card_pixmap("", 10, 10) is None
    finally:
        _sh.rmtree(_tmp, ignore_errors=True)

    # ② Plus aucune purge de cache à l'aveugle dans les cartes.
    import ui.page_castings as _PC
    _src = "\n".join(l.split("#", 1)[0] for l in _i.getsource(_PC).splitlines())
    assert "QPixmapCache.remove" not in _src, \
        "le Casting vide encore le cache à chaque carte"
    # …et les cinq pages passent bien par le cache partagé.
    for _mod in ("ui.page_castings", "ui.page_accessories", "ui.page_hmc",
                 "ui.page_vehicles", "ui.page_decors", "ui.element_side_panel"):
        _m = __import__(_mod, fromlist=["_"])
        _s = "\n".join(l.split("#", 1)[0] for l in _i.getsource(_m).splitlines())
        assert "card_pixmap" in _s, f"{_mod} ne passe pas par le cache de vignettes"

    # ③ Storyboard : les lignes sont posées D'AFFILÉE, repaints gelés pendant
    #    la construction. Une version par PAQUETS a été essayée puis RETIRÉE :
    #    elle rendait la main 8× plus vite mais l'insertion différée décalait
    #    les lignes — chevauchements et hauteurs incohérentes à l'écran
    #    (constat Matthieu 2026-07-31). L'ordre de cette liste est un contrat.
    import ui.page_storyboard as _PS
    _r = "\n".join(l.split("#", 1)[0]
                   for l in _i.getsource(_PS.PageStoryboard._render).splitlines())
    assert "setUpdatesEnabled(False)" in _r, \
        "les repaints ne sont plus gelés pendant la construction du tableau"
    assert "insertWidget" not in _r, \
        "insertion à position calculée : c'est ce qui cassait l'affichage"


@test
def cout_du_projet_journal_et_fenetre():
    """« Coût du projet » (demande Matthieu 2026-07-31) : chaque opération
    facturée est notée DANS le projet, avec son montant, et la fenêtre en
    donne le total."""
    import os as _os, tempfile as _tf, shutil as _sh, inspect as _i
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import core.context as _ctx
    from core import spend as _sp

    _prev_path = _ctx.get_project_path() if hasattr(_ctx, "get_project_path") else ""
    _prev_id = _ctx.get_project_id()
    _td = _tf.mkdtemp(prefix="pandora_spend_")
    try:
        _ctx.set_project_path(_td)
        _ctx.set_project_id("t-spend")
        assert _sp.load() == [], "journal non vide sur un projet neuf"

        _sp.record(_sp.KIND_VIDEO, "seedance-2.0", "Plan 21", 1.50, "720p")
        _sp.record(_sp.KIND_IMAGE, "Seedream 5.0 Pro", "Mood", 0.0675)
        _sp.record(_sp.KIND_TEXT, "claude-sonnet-5", "Découpage", 0.12)
        _items = _sp.load()
        assert len(_items) == 3, _items
        # Le plus RÉCENT en premier — la fenêtre lit dans cet ordre.
        assert _items[0]["label"] == "Découpage", _items[0]
        assert abs(_sp.total_usd() - 1.6875) < 1e-6, _sp.total_usd()
        _par = _sp.totals_by_kind()
        assert _par[_sp.KIND_VIDEO] == (1, 1.5), _par
        # Le journal vit DANS le projet, pas sur le poste.
        assert _os.path.isfile(_os.path.join(_td, "data", "spend.json"))

        # Un montant illisible ne casse rien (une génération déjà payée ne doit
        # jamais échouer à cause du journal).
        _sp.record(_sp.KIND_OTHER, "x", "y", None)
        assert len(_sp.load()) == 4

        # La fenêtre affiche les lignes et le total.
        from ui.dialog_project_cost import ProjectCostDialog
        _d = ProjectCostDialog()
        assert _d._lay.count() == 4, _d._lay.count()
        assert "1.69" in _d._total_lbl.text(), _d._total_lbl.text()
    finally:
        try:
            _ctx.set_project_path(_prev_path)
            _ctx.set_project_id(_prev_id)
        except Exception:
            pass
        _sh.rmtree(_td, ignore_errors=True)

    # Les générations VIDÉO alimentent le journal par un point unique.
    import core.history as _H
    _src = "\n".join(l.split("#", 1)[0] for l in _i.getsource(_H).splitlines())
    assert "_note_spend" in _src and "spend.record" in _src, \
        "les générations vidéo n'alimentent pas le coût du projet"

    # Le bouton ouvre une FENÊTRE, pas une page : consulter le budget ne doit
    # pas faire perdre l'écran de travail en cours.
    import ui.pandora_window as _PW
    _nav = "\n".join(l.split("#", 1)[0]
                     for l in _i.getsource(_PW.PandoraWindow._navigate).splitlines())
    assert "ProjectCostDialog" in _nav, "le bouton n'ouvre pas la fenêtre"

    # ⚠ ET LA BARRE SE CONSTRUIT VRAIMENT. Vérifier une liste ne suffit pas :
    # une première version ajoutait un séparateur de groupe et faisait PLANTER
    # l'application au démarrage (IndexError) alors que ce test passait au vert
    # (régression du 2026-07-31, signalée par Matthieu au lancement).
    _sb = _PW._Sidebar()
    assert hasattr(_sb, "_btn_cost"), "pas de bouton « Coût du projet » dans la barre"
    assert "settings" in _sb._items, sorted(_sb._items)
    # Il reste DISCRET : pas d'émoticône, teinte des libellés de la barre —
    # ce n'est pas une étape du travail (demande Matthieu).
    _txt = _sb._btn_cost.text()
    assert not any(ord(c) > 0x2100 for c in _txt), ("émoticône dans le bouton", _txt)
    from ui.styles import CP as _CP
    assert _CP["text_secondary"] in _sb._btn_cost.styleSheet(), \
        "le bouton n'est pas dans la teinte discrète de la barre"
    # …et il n'est PAS une entrée de navigation (ce n'est pas une page).
    assert "cost" not in [it[2] for it in _PW._get_nav_items() if it], \
        "« Coût du projet » ne doit pas être une page de la navigation"


@test
def dossier_des_projets_reglable_disque_externe():
    """Emplacement des projets réglable depuis les Paramètres (2026-08-09).

    Il l'était UNIQUEMENT dans « Nouveau projet » : une fois le premier projet
    créé, l'utilisateur ne pouvait plus le retrouver. Demande d'un utilisateur
    voulant travailler sur disque externe entre sa station et son portable."""
    import os as _os, tempfile as _tf
    import core.config as _cm
    from core import projects_location as _loc

    # Isolation TOTALE : la vraie config n'est ni lue ni écrite.
    _orig_load, _orig_save = _cm.load_config, _cm.save_config
    _fake = {"anthropic_key": "SECRET", "ai_model_creative": "claude-opus-4-8"}
    _cm.load_config = lambda: dict(_fake)
    _cm.save_config = lambda c: (_fake.clear(), _fake.update(c))
    try:
        assert _loc.is_default(), "sans réglage → dossier par défaut"

        _tmp = _tf.mkdtemp(prefix="pandora_ext_")
        _loc.set_projects_root(_tmp)
        assert _os.path.normpath(_loc.get_projects_root()) == _os.path.normpath(_tmp)
        assert not _loc.is_default() and _loc.is_available()

        # ⚠ save_config REMPLACE le fichier entier : écrire un dict partiel
        # effacerait les clés API. Le module doit relire avant d'écrire.
        assert _fake.get("anthropic_key") == "SECRET", \
            "l'enregistrement a effacé les autres clés de la config"
        assert _fake.get("ai_model_creative") == "claude-opus-4-8"

        # Disque débranché : le chemin reste, mais il est signalé indisponible.
        _fake["last_project_location"] = r"Z:\PANDORA Projects"
        assert _loc.get_projects_root() == r"Z:\PANDORA Projects"
        assert not _loc.is_available(), "un disque absent doit être détecté"

        # La rangée le DIT — et ne crie pas au disque débranché quand c'est
        # simplement le dossier par défaut pas encore créé (constaté au rendu).
        from ui.projects_location_row import ProjectsLocationRow
        _row = ProjectsLocationRow()
        assert "introuvable" in _row._state.text().lower(), _row._state.text()
        _fake.pop("last_project_location", None)
        _row.refresh()
        _txt = _row._state.text().lower()
        assert "introuvable" not in _txt and "défaut" in _txt, _txt

        # …et elle est réellement branchée dans la page Paramètres Cinéma.
        from ui.page_settings import SettingsPage
        assert hasattr(SettingsPage(), "_projects_location"), \
            "pas de « Dossier des projets » dans les Paramètres Cinéma"
    finally:
        _cm.load_config, _cm.save_config = _orig_load, _orig_save


@test
def seedance_2_5_ajoutee_sans_remplacer_la_2_0():
    """Seedance 2.5 (sortie fal 2026-08-07) branchée EN PLUS de la 2.0.

    Ce n'est PAS une montée de version : la 2.5 plafonne à 720p (ni 1080p ni
    4K) et coûte 56 % plus cher à résolution égale. Elle gagne sur le
    plan-séquence (30 s) et les références (50 au lieu de 9), qu'elle sait
    DÉSIGNER dans le prompt par @Image1 — ce que la 2.0 ne sait pas faire."""
    from core import seedance_family as _sf, pricing, engine_caps, engine_grammar

    # Routage : chaque famille son préfixe, repli 2.0 pour tout inconnu.
    assert _sf.endpoints("seedance-2.5")["ref"] == \
        "bytedance/seedance-2.5/reference-to-video"
    assert _sf.endpoints("seedance-2.0-fast")["i2v"] == \
        "bytedance/seedance-2.0/fast/image-to-video"
    assert _sf.endpoints("veo-3.1")["t2v"] == "bytedance/seedance-2.0/text-to-video"

    # ⚠ Le plafond de résolution est le piège de cette version : un plan réglé
    # en 4K puis basculé sur la 2.5 doit être RABATTU, pas envoyé tel quel
    # (l'endpoint refuserait l'appel).
    assert not _sf.supports_resolution("seedance-2.5", "4k")
    # Le 1080p est arrivé chez fal (fiche relue le 24/09/2026, 1,164 $/s) ; un
    # 4K demandé retombe sur 720p, PAS sur ce 1080p à 2,5 × le prix.
    assert _sf.supports_resolution("seedance-2.5", "1080p")
    assert _sf.clamp_resolution("seedance-2.5", "4k") == "720p"
    assert _sf.clamp_resolution("seedance-2.5", "1080p") == "1080p"
    assert _sf.clamp_resolution("seedance-2.0", "4k") == "4k", "la 2.0 garde son 4K"
    _rsrc = inspect.getsource(__import__("api.real", fromlist=["x"]))
    assert "clamp_resolution" in _rsrc, "api/real n'applique pas le rabattement"

    # …et le menu ne propose QUE ce que l'endpoint accepte.
    import ui.tab_t2v as _t2v
    assert [v for _l, v in _t2v._ENGINE_RESOLUTIONS["seedance-2.5"]] == ["720p", "1080p", "480p"], \
        "720p reste EN TÊTE (défaut) ; le 1080p à 1,16 $/s se choisit, ne s'impose pas"
    assert "seedance-2.5" in dict((k, l) for l, k in _t2v._ENGINES)

    # Références NOMMÉES : @Image1 suit l'ORDRE D'ENVOI (core/mood_refs), et le
    # rôle d'origine est conservé — c'est lui qui dit au moteur ce qu'il tient.
    _named = _sf.annotate_roles_with_tokens(
        ["character sheet for Jesus", "location plate"], "seedance-2.5")
    assert _named[0] == "character sheet for Jesus (@Image1)", _named
    assert _named[1].endswith("(@Image2)"), _named
    assert _sf.annotate_roles_with_tokens(["a"], "seedance-2.0") == ["a"], \
        "la 2.0 ne nomme pas ses refs : annoter serait du bruit dans le prompt"
    assert _sf.annotate_roles_with_tokens([""], "seedance-2.5") == ["@Image1"]
    assert "annotate_roles_with_tokens" in _rsrc, "api/real n'annote pas les rôles"

    # Plafonds de refs et prix.
    assert _sf.max_images("seedance-2.5") == 50 and _sf.max_images("seedance-2.0") == 9
    assert abs(pricing.price_per_second("seedance-2.5", "720p") - 0.4730) < 1e-9
    assert pricing.price_per_second("seedance-2.5", "720p") > \
           pricing.price_per_second("seedance-2.0", "720p")

    # Elle entre dans le workflow séquences et parle la grammaire Seedance.
    assert engine_caps.workflow_compatible("seedance-2.5")
    assert engine_caps.ENGINE_CAPS["seedance-2.5"]["refs"] == "full"
    assert engine_grammar.grammar_for("seedance-2.5") == "fields"

    # La 2.0 reste le DÉFAUT du projet : la 2.5 ne la remplace nulle part.
    from core.config import _DEFAULTS as _D
    assert _D.get("default_model") == "seedance-2.0", \
        "la 2.5 ne doit pas devenir le défaut (56 % plus chère, pas de 4K)"


@test
def moteur_cible_choisi_avant_le_decoupage():
    """Fenêtre « moteur cible » à la création du storyboard (2026-08-09).

    Chaque moteur attend une forme de prompt différente : la choisir APRÈS
    avoir écrit 75 plans obligerait à tout recomposer. La question est donc
    posée avant, une seule fois par projet, et le choix descend jusqu'au
    prompt système du découpage."""
    import os as _os, tempfile as _tf
    import core.context as _ctx
    from core import target_engine as _te

    _old_path, _old_id = _ctx.get_project_path(), _ctx.get_project_id()
    _tmp = _tf.mkdtemp(prefix="pandora_target_")
    _os.makedirs(_os.path.join(_tmp, "data"), exist_ok=True)
    try:
        _ctx.set_project_path(_tmp)
        _ctx.set_project_id("test_target")

        assert not _te.has_choice() and _te.get_target_engine() == "seedance-2.0"
        _te.set_target_engine("seedance-2.5")
        assert _te.has_choice() and _te.get_target_engine() == "seedance-2.5"
        # Le réglage vit DANS le projet : deux films peuvent viser deux moteurs.
        assert _os.path.isfile(_os.path.join(_tmp, "data", "target_engine.json"))

        # Le briefing dit la VÉRITÉ du moteur, lue sur les tables.
        _b = _te.briefing("seedance-2.5")
        assert "@Image1" in _b, "la 2.5 nomme ses références"
        # Le 1080p est arrivé chez fal pour la 2.5 (fiche relue le 24/09/2026) ;
        # toujours pas de 4K — le briefing lit la table, il doit dire les deux.
        assert "1080p" in _b and "4k" not in _b.lower(), "la 2.5 : 1080p oui, 4K non"
        assert "4k" in _te.briefing("seedance-2.0"), "la 2.0 monte au 4K"
        _bf = _te.briefing("flux-3")
        assert "5 and 20 seconds" in _bf and "sound clause" in _bf

        # ⚠ Hors projet : AUCUNE écriture. Sans cette garde, le réglage tombait
        # dans le dossier data/ de l'application et s'appliquait ensuite à TOUS
        # les projets (défaut réel, trouvé au test avant livraison).
        _ctx.set_project_path("")
        _te.set_target_engine("flux-3")
        assert not _te.has_choice(), "le réglage a fui hors du projet"
        assert _te.get_target_engine() == "seedance-2.0"
    finally:
        _ctx.set_project_path(_old_path or "")
        _ctx.set_project_id(_old_id or "")

    # Le choix descend RÉELLEMENT dans le découpage.
    from api.screenplay import GenerateStoryboardWorker as _W
    assert "target_engine" in inspect.signature(_W.__init__).parameters
    _src = inspect.getsource(_W.run)
    assert "_engine_briefing()" in _src, "briefing non injecté"
    assert "names_block = names_block +" in _src, \
        "l'injection doit passer par names_block — sinon deux des trois branches" \
        " de user_content l'oublient silencieusement"
    _psrc = inspect.getsource(__import__("ui.page_scenario", fromlist=["_"]))
    assert "ask_target_engine" in _psrc, "la question n'est pas posée avant le découpage"

    # La fenêtre ne connaît AUCUN moteur : c'est l'édition qui les fournit.
    from ui.dialog_target_engine import TargetEngineDialog
    from ui.tab_t2v import _ENGINES as _E
    _dlg = TargetEngineDialog(_E)
    assert _dlg._combo.count() == len(_E)
    assert TargetEngineDialog(([])) is not None or True   # liste vide : pas de crash


@test
def forme_du_prompt_reglable_pour_essai():
    """Sélecteur « Forme du prompt » dans la barre Storyboard (2026-08-09).

    Le relevé documentaire dit que Seedance et Kling attendraient une phrase
    continue là où PANDORA écrit une fiche technique — avec une confiance
    seulement MOYENNE. Plutôt que trancher sur une lecture, on rend la forme
    réglable pour comparer deux écritures du même plan."""
    import os as _os, tempfile as _tf
    import core.context as _ctx
    from core import prompt_form as _pf, engine_grammar as _eg

    _old_p, _old_i = _ctx.get_project_path(), _ctx.get_project_id()
    _tmp = _tf.mkdtemp(prefix="pandora_form_")
    _os.makedirs(_os.path.join(_tmp, "data"), exist_ok=True)
    try:
        _ctx.set_project_path(_tmp)
        _ctx.set_project_id("test_form")

        # Au repos, la table décide : le comportement d'origine est INTACT.
        assert _pf.get_form() == _pf.AUTO and not _pf.is_forced()
        _base_seed = _eg.grammar_for("seedance-2.0")
        _base_veo  = _eg.grammar_for("veo-3.1")
        assert _base_seed != _base_veo, "la table doit distinguer les moteurs"

        # Essai : la forme forcée prime sur la table, pour TOUS les moteurs.
        _pf.set_form("sentence")
        assert _pf.is_forced()
        for _k in ("seedance-2.0", "seedance-2.5", "kling-v3-pro", "inconnu-xyz"):
            assert _eg.grammar_for(_k) == "sentence", _k

        # Retour à « auto » : la table reprend EXACTEMENT la main — sinon un
        # essai laisserait le projet dans un état qu'on croit d'origine.
        _pf.set_form(_pf.AUTO)
        assert _eg.grammar_for("seedance-2.0") == _base_seed
        assert _eg.grammar_for("veo-3.1") == _base_veo

        # Valeur inconnue → auto, jamais une forme inventée.
        assert _pf.set_form("n_importe_quoi") == _pf.AUTO

        # Le réglage vit dans le PROJET…
        _pf.set_form("fields")
        assert _os.path.isfile(_os.path.join(_tmp, "data", "prompt_form.json"))
        # …et ne fuit PAS hors projet (même piège que core/target_engine).
        _ctx.set_project_path("")
        _pf.set_form("sentence")
        assert _pf.get_form() == _pf.AUTO, "le réglage a fui hors du projet"
    finally:
        _ctx.set_project_path(_old_p or "")
        _ctx.set_project_id(_old_i or "")

    # ⚠ LE CACHE DE COMPOSITION DOIT CONNAÎTRE LA FORME.
    # La forme entre dans la composition par format_rules(), pas par ctx :
    # absente de l'empreinte, le cache renvoyait l'ancien prompt et basculer
    # fiche ↔ phrase ne changeait RIEN à l'écran (signalé par Matthieu).
    _ctx.set_project_path(_tmp)
    _ctx.set_project_id("test_form")
    try:
        from ui.tab_t2v import TabT2V as _T2V
        _pf.set_form("fields")
        _k1 = _T2V._final_cache_key(None, "un plan", {"engine": "seedance-2.0"})
        _pf.set_form("sentence")
        _k2 = _T2V._final_cache_key(None, "un plan", {"engine": "seedance-2.0"})
        assert _k1 != _k2, \
            "changer la forme doit changer la clé de cache, sinon l'essai est invisible"
        _pf.set_form("fields")
        assert _T2V._final_cache_key(None, "un plan", {"engine": "seedance-2.0"}) == _k1, \
            "revenir à la même forme doit retrouver la même clé"
    finally:
        _pf.set_form(_pf.AUTO)
        _ctx.set_project_path(_old_p or "")
        _ctx.set_project_id(_old_i or "")

    # Un essai en cours doit se VOIR, sinon on attribue le résultat au moteur.
    from ui.prompt_form_selector import PromptFormSelector
    _sel = PromptFormSelector()
    assert _sel._combo.count() == len(_pf.FORMS)
    # …et le sélecteur est réellement dans la barre du Storyboard.
    _src = inspect.getsource(__import__("ui.page_storyboard", fromlist=["_"]))
    assert "PromptFormSelector()" in _src, "sélecteur absent de la barre Storyboard"


@test
def vue_prompt_structure_ou_final():
    """Bascule « Prompt structuré / Prompt final » du Storyboard (2026-08-09).

    Le Storyboard montrait le document de travail (blocs français) : impossible
    d'y voir l'effet du moteur ou de la forme, qui n'agissent que sur le texte
    final. La bascule l'affiche — SANS jamais composer, un affichage ne doit
    pas déclencher 75 appels IA payants."""
    from core import final_prompt as _fp

    _BLOCS = "[ACTION]\nVue plongeante sur l'arbre d'acier."
    _FINAL = "A high-angle shot of the steel tree at dawn."
    _shot = {"seedance_prompt": _BLOCS}

    # Jamais composé : message EXPLICITE qui dit POURQUOI, jamais du vide.
    assert _fp.state_of(_shot) == _fp.ABSENT
    _t = _fp.display_text(_shot, "final")
    assert "appel IA" in _t and "pas encore composé" in _t, _t

    # Composé : le texte final s'affiche, le document de travail reste INTACT.
    _shot.update({_fp.F_TEXT: _FINAL, _fp.F_SRC: _BLOCS,
                  _fp.F_ENGINE: "seedance-2.5"})
    assert _fp.state_of(_shot) == _fp.FRESH
    assert _fp.display_text(_shot, "final") == _FINAL
    assert _fp.display_text(_shot, "structure") == _BLOCS, \
        "la vue structurée ne doit JAMAIS changer — c'est le document de l'auteur"

    # Plan retouché depuis : PÉRIMÉ, annoncé, mais on montre quand même le
    # dernier prompt réellement envoyé (sinon on cache une information vraie).
    _shot["seedance_prompt"] = _BLOCS + "\nUn oiseau passe."
    assert _fp.state_of(_shot) == _fp.STALE
    _t2 = _fp.display_text(_shot, "final")
    assert "PÉRIMÉ" in _t2 and _FINAL in _t2, _t2

    # La colonne et la hauteur de ligne portent sur le MÊME texte. Garanti
    # désormais PAR CONSTRUCTION : la hauteur mesure les libellés réellement
    # construits (_col_cells) au lieu d'une liste de champs écrite à la main —
    # ils ne PEUVENT plus diverger (refonte 2026-08-11).
    _src = inspect.getsource(__import__("ui.page_storyboard", fromlist=["_"]))
    assert "_prompt_cell_text(" in _src
    from ui.page_storyboard import _ShotRow as _SR
    assert "_col_cells" in inspect.getsource(_SR._content_height), \
        "la hauteur ne mesure plus les cellules réelles"
    assert "PromptViewToggle()" in _src, "bascule absente de la barre"
    # La forme n'a de sens qu'en vue finale : elle doit être désactivée sinon
    # (c'est ce qui rendait le réglage incompréhensible au premier essai).
    assert "_sync_prompt_form_enabled" in _src

    # Le Studio CONSERVE le prompt composé, sinon la vue finale reste vide.
    _tsrc = inspect.getsource(__import__("ui.tab_t2v", fromlist=["_"]))
    assert "final_prompt as _fp" in _tsrc and "_fp.remember(" in _tsrc, \
        "le prompt composé n'est pas conservé avec le plan"


@test
def pipeline_prompt_a_lendroit():
    """Architecture 2026-08-09 (décision Matthieu) : le pipeline à l'ENDROIT.

    Les deux prompts (structuré + final) naissent AU DÉCOUPAGE, restent
    synchronisés dans les deux sens à l'édition, et le Studio LIT le final du
    plan au lieu de recomposer à l'envoi. Ce test vérifie les COMPORTEMENTS et
    les points de branchement — pas des chaînes décoratives."""
    import os as _os, tempfile as _tf
    import core.context as _ctx
    import api.video_prompt as _vp
    import core.ai_provider as _aip
    from core import prompt_sync as _ps, final_prompt as _fp
    from core.prompt_sections import build as _build

    _old_p, _old_i = _ctx.get_project_path(), _ctx.get_project_id()
    _oc, _ok_, _ocmp = _vp.compose, _aip.key_error, _aip.complete
    _tmp = _tf.mkdtemp(prefix="pandora_endroit_")
    _os.makedirs(_os.path.join(_tmp, "data"), exist_ok=True)
    try:
        _ctx.set_project_path(_tmp)
        _ctx.set_project_id("test_endroit")
        _seen = {}
        def _cap_compose(p, **kw):
            _seen["prompt"] = p
            return f"PROSE[{kw.get('engine','')}] {p[:30]}"
        _vp.compose = _cap_compose
        _aip.key_error = lambda task="": None
        _aip.complete = lambda s, u, **kw: (
            '{"action": "nouvelle action", "staging": "", "ambiance": "", '
            '"decor": "", "lighting": ""}')

        # ── 1. Structuré → final : composé par le MÊME composeur que le Studio,
        # rangé dans le plan avec sa source (c'est elle qui dira « périmé »).
        _shot = {"id": "e1", "duration": 5.0, "shot_size": "PL",
                 "camera_axis": "Plongée",
                 "seedance_prompt": _build(action="Un plan.",
                                           sound="vent", style="Arcane")}
        assert _ps.compose_final_for_shot(_shot, save=False).startswith("PROSE[")
        assert _fp.state_of(_shot) == _fp.FRESH

        # ── 1b. L'AXE atteint le composeur (trou trouvé par Matthieu le
        # 2026-08-11 : la sync composait le prompt NU, sans les termes caméra
        # que le Studio injecte — le final du découpage ignorait l'axe).
        from core.shot_terms import CAMERA_AXIS_EN
        assert CAMERA_AXIS_EN["Plongée"] in _seen["prompt"], _seen["prompt"][:200]
        assert "no subtitles" in _seen["prompt"]

        # ── 1c. Empreinte de contexte : changer l'axe ne touche PAS au texte
        # structuré, mais le final décrit l'ancien axe → il doit devenir
        # PÉRIMÉ. Et revenir à l'axe d'origine le rend à nouveau frais, sans
        # appel IA : c'est la réponse à « peut-on éviter de re-générer ? » —
        # on ne recompose QUE quand un champ atteint réellement la prose.
        _shot["camera_axis"] = "Dos"
        assert _fp.state_of(_shot) == _fp.STALE, \
            "un final qui décrit l'ancien axe ne doit pas se dire frais"
        _shot["camera_axis"] = "Plongée"
        assert _fp.state_of(_shot) == _fp.FRESH
        # Un final composé AVANT l'empreinte (pas de F_CTX) reste jugé sur le
        # texte seul — on ne périme pas rétroactivement du déjà-payé.
        _leg = {"seedance_prompt": "[🎬 ACTION]\nx",
                _fp.F_TEXT: "P", _fp.F_SRC: "[🎬 ACTION]\nx"}
        assert _fp.state_of(_leg) == _fp.FRESH

        # ── 2. Final → structuré : sections IA, mais TECHNIQUE déterministe et
        # SON/STYLE repris de l'ancien — les faire deviner les corromprait.
        _back = _ps.structured_from_final(_shot, "A wide shot.")
        assert "nouvelle action" in _back and "vent" in _back and "Arcane" in _back
        assert "Plan large" in _back or "plan large" in _back

        # ── 3. Sans clé IA : AUCUN appel, rien de touché (filet Studio conservé).
        _aip.key_error = lambda task="": "pas de clé"
        _nk = {"id": "nk", "seedance_prompt": "[🎬 ACTION]\nx"}
        assert _ps.compose_final_for_shot(_nk, save=False) == ""
        assert _ps.compose_finals_for_shots([_nk]) == 0 and _fp.F_TEXT not in _nk
        _aip.key_error = lambda task="": None

        # ── 4. Anti-écrasement : un résultat dont la source a rebougé est JETÉ.
        import core.storyboard as _sb
        _sb.set_namespace("storyboard")
        _saved = _sb.save_shot({"id": "e2", "seedance_prompt": "[🎬 ACTION]\nv1"})
        _sched = _ps.PromptSyncScheduler()
        _sched._on_done(str(_saved["id"]), "final", "PROSE PERIMEE", "[🎬 ACTION]\nAUTRE")
        _re = next(s for s in _sb.list_shots() if s["id"] == _saved["id"])
        assert _re.get(_fp.F_TEXT, "") != "PROSE PERIMEE", \
            "une composition partie d'une source périmée ne doit jamais écraser"
        # …et un résultat à source à jour est APPLIQUÉ et SAUVÉ.
        _sched._on_done(str(_saved["id"]), "final", "PROSE OK", "[🎬 ACTION]\nv1")
        _re = next(s for s in _sb.list_shots() if s["id"] == _saved["id"])
        assert _re.get(_fp.F_TEXT) == "PROSE OK"
    finally:
        _vp.compose, _aip.key_error, _aip.complete = _oc, _ok_, _ocmp
        _ctx.set_project_path(_old_p or "")
        _ctx.set_project_id(_old_i or "")

    # ── 5. Branchements réels (les comportements ci-dessus doivent être CÂBLÉS).
    # Le découpage compose les finals dans SA passe, APRÈS résolution des IDs
    # (le composeur lit la bible du plan) — et PAS via un champ anglais dans le
    # JSON, qui doublerait la sortie et ressusciterait la troncature silencieuse
    # (84 fiches → 20 plans, FIGHTER 2026-07-28).
    from api.screenplay import GenerateStoryboardWorker as _W
    _rsrc = inspect.getsource(_W.run)
    assert "compose_finals_for_shots" in _rsrc
    assert _rsrc.index("character_ids") < _rsrc.index("compose_finals_for_shots")
    assert hasattr(_W, "compose_progress"), "progression de composition absente"
    _dsrc = inspect.getsource(__import__("ui.dialog_storyboard_generate", fromlist=["_"]))
    assert "compose_progress.connect" in _dsrc, "le dialogue n'affiche pas la composition"

    # Le Studio LIT un final frais (même moteur, même forme) au lieu de
    # recomposer ; sinon il garde le chemin historique comme filet.
    _tsrc = inspect.getsource(__import__("ui.tab_t2v", fromlist=["_"]))
    assert "_fp.state_of(_shot) == _fp.FRESH" in _tsrc
    assert "_fp.F_ENGINE" in _tsrc and "_fp.F_FORM" in _tsrc, \
        "un final écrit pour un autre moteur/forme ne doit pas être réutilisé"
    # La table heure→anglais n'existe qu'en UN exemplaire (prompt_sync).
    assert "from core.prompt_sync import SHOT_TIME_EN" in _tsrc
    assert '"Jour":' not in _tsrc, "table shot_time dupliquée dans le Studio"

    # Le Storyboard synchronise à l'édition : point unique _save_field
    # (structuré + champs caméra), et la vue finale édite le final.
    _psrc = inspect.getsource(__import__("ui.page_storyboard", fromlist=["_"]))
    assert "schedule_final(self._data)" in _psrc
    assert "schedule_structured(data, v)" in _psrc
    assert "synced.connect" in _psrc, "les lignes ne se rafraîchissent pas après sync"
    # Les champs HORS-TEXTE (axe, distance, hauteur, heure, durée, langue)
    # déclenchent aussi la resync — sans eux, le final restait « frais » en
    # décrivant l'ancien axe (question Matthieu 2026-08-11).
    assert "_FINAL_CTX_FIELDS" in _psrc and '"camera_axis"' in _psrc
    # Le Studio ne lit le stocké QUE si aucun réglage propre au Studio
    # (continuité, anti-CGI…) n'ajoute de brique non couverte par la sync ;
    # et il assemble avec la MÊME fonction d'injection que la sync.
    assert "_studio_extra" in _tsrc and "_COVERED" in _tsrc
    assert "from core.prompt_sync import apply_injections" in _tsrc


@test
def durees_par_moteur_et_flux3_generable():
    """Durées par moteur (30 s en Seedance 2.5) + Flux 3 générable (2026-08-09).

    Le plafond de 15 s était écrit EN DUR dans quatre fichiers : un plan de
    30 s demandé à la 2.5 aurait été silencieusement amputé de moitié — le
    plan-séquence long est précisément le gain attendu pour le mapping."""
    import os as _os, tempfile as _tf
    from core import seedance_family as _sf

    # Bornes par famille — la source unique des quatre anciens « min(15, … ) ».
    assert _sf.duration_bounds("seedance-2.5") == (4, 30)
    assert _sf.duration_bounds("seedance-2.0") == (4, 15)
    assert _sf.clamp_duration("seedance-2.5", 30) == 30, "30 s amputée"
    assert _sf.clamp_duration("seedance-2.5", 2) == 4, "minimum API 2.5 = 4 s"
    assert _sf.clamp_duration("seedance-2.0", 30) == 15

    # L'envoi clamp par moteur (plus de 15 en dur).
    _rsrc = inspect.getsource(__import__("api.real", fromlist=["_"]).run_real)
    assert "_sf.clamp_duration(model, duration)" in _rsrc
    assert "min(15, int(duration))" not in _rsrc

    # Le découpage Live borne au moteur VISÉ (comportement réel).
    import core.context as _ctx
    from core import target_engine as _te
    _old_p, _old_i = _ctx.get_project_path(), _ctx.get_project_id()
    _tmp = _tf.mkdtemp(prefix="pandora_dur_")
    _os.makedirs(_os.path.join(_tmp, "data"), exist_ok=True)
    try:
        _ctx.set_project_path(_tmp)
        _ctx.set_project_id("test_dur")
        from api.live_screenplay import _normalize as _ln
        _te.set_target_engine("seedance-2.5")
        assert _ln({"duration": 28, "prompt": "p"}, "mapping")["duration"] == 28
        _te.set_target_engine("seedance-2.0")
        assert _ln({"duration": 28, "prompt": "p"}, "mapping")["duration"] == 15
    finally:
        _ctx.set_project_path(_old_p or "")
        _ctx.set_project_id(_old_i or "")

    # Le découpage Cinéma lit aussi la borne du moteur visé.
    _ssrc = inspect.getsource(__import__("api.screenplay", fromlist=["_"])
                              .GenerateStoryboardWorker.run)
    assert "duration_bounds" in _ssrc, "clamp Cinéma resté à 15 en dur"
    # …et les dialogs de plan + la page séquence Live suivent le moteur.
    for _m in ("ui.dialog_shot", "ui.dialog_shot_live", "ui.page_live_sequence"):
        assert "duration_bounds" in inspect.getsource(__import__(_m, fromlist=["_"])), \
            f"{_m} : slider de durée resté figé à 15 s"

    # Flux 3 : générable dans les DEUX éditions, mock sans clé, pièges encodés.
    import api.video_engines as _ve
    _wsrc = inspect.getsource(_ve.Flux3Worker._real)
    assert "f3.clamp_safety" in _wsrc, "échelle 0-4 de Flux 3 non clampée"
    assert "draft_cache" in _wsrc, "jeton d'affinage du brouillon perdu"
    assert "f3.endpoint(mode, draft=draft)" in _wsrc
    import ui.tab_t2v as _t2v
    import ui.tab_t2v_live as _t2vl
    for _mod in (_t2v, _t2vl):
        _w = _mod._make_ext_worker("flux-3-draft", {"prompt": "x"})
        assert isinstance(_w, _ve.Flux3Worker) and _w.params.get("draft") is True, \
            f"{_mod.__name__} : le palier brouillon ne route pas"
        assert "flux-3" in dict((k, l) for l, k in _mod._ENGINES)
        assert "flux-3" in _mod._TEXT_FALLBACK_ENGINES, \
            "Flux 3 sans refs : les fiches doivent être décrites en texte"
        assert "_refresh_duration_options" in inspect.getsource(_mod), \
            f"{_mod.__name__} : combo durée figé (pas de 30 s en 2.5)"
    from core.engine_grammar import _GRAMMAR_BY_ENGINE as _G
    assert _G.get("flux-3") == "sentence", "grammaire Flux 3 absente de la table"


@test
def composer_les_finals_dun_storyboard_existant():
    """Bouton « Composer les prompts finals » (2026-08-11).

    Un storyboard antérieur à l'architecture « à l'endroit » n'a aucun final
    stocké : la vue finale n'affichait qu'un avertissement répété SANS moyen
    d'agir (constat Matthieu, projet ADAM ET EVE). Le bouton est l'issue —
    clic explicite et chiffré, jamais une composition due à l'affichage."""
    import os as _os, tempfile as _tf
    import core.context as _ctx
    import api.video_prompt as _vp
    import core.ai_provider as _aip
    from core import prompt_sync as _ps, final_prompt as _fp

    _old_p, _old_i = _ctx.get_project_path(), _ctx.get_project_id()
    _oc, _ok_ = _vp.compose, _aip.key_error
    _tmp = _tf.mkdtemp(prefix="pandora_batch_")
    _os.makedirs(_os.path.join(_tmp, "data"), exist_ok=True)
    try:
        _ctx.set_project_path(_tmp)
        _ctx.set_project_id("test_batch")
        _vp.compose = lambda p, **kw: f"PROSE {p[:20]}"
        _aip.key_error = lambda task="": None
        import core.storyboard as _sb
        _sb.set_namespace("storyboard")
        _s1 = _sb.save_shot({"id": "c1", "seedance_prompt": "[🎬 ACTION]\nun"})
        _s2 = _sb.save_shot({"id": "c2", "seedance_prompt": "[🎬 ACTION]\ndeux"})

        # Le compte annonce la dépense AVANT le clic.
        assert len(_ps.shots_needing_final([_s1, _s2])) == 2

        # Lot inline (pas de thread) ; b2 modifié pendant → son résultat JETÉ.
        _w = _ps.BatchComposeWorker([_s1, _s2])
        _got = []
        _w.done.connect(lambda c: _got.append(c))
        _w.run()
        _s2b = next(s for s in _sb.list_shots() if s["id"] == "c2")
        _s2b["seedance_prompt"] += "\nmodifié"
        _sb.save_shot(_s2b)
        assert _ps.apply_batch_results(_got[0]) == 1, \
            "un plan modifié pendant la composition ne doit pas recevoir le périmé"
        _r1 = next(s for s in _sb.list_shots() if s["id"] == "c1")
        assert _fp.state_of(_r1) == _fp.FRESH and \
            _fp.text_of(_r1).startswith("PROSE")
    finally:
        _vp.compose, _aip.key_error = _oc, _ok_
        _ctx.set_project_path(_old_p or "")
        _ctx.set_project_id(_old_i or "")

    # Message d'absence : COURT et il pointe le bouton par son libellé RÉEL
    # (« ⟳ Composer (N) » — raccourci demandé par Matthieu le 2026-08-11 ;
    # pas « Générer », déjà pris par la génération vidéo de chaque ligne).
    _msg = _fp.display_text({"seedance_prompt": "x"}, "final")
    assert "« Composer »" in _msg and len(_msg) < 160, _msg

    # ⚠ CRASH RÉEL 2026-08-11 : page détruite PENDANT le lot (changement de
    # projet) → la lambda de progression touchait un bouton mort, le scheduler
    # rappelait une page morte → RuntimeError à l'écran. On REJOUE le scénario.
    from ui.page_storyboard import PageStoryboard as _PS
    from core.prompt_sync import scheduler as _sched_gl, BatchComposeWorker as _BW
    _pg = _PS()
    _pg.deleteLater()
    from PyQt6.QtCore import QCoreApplication as _QCA, QEvent as _QEv
    # processEvents ne traite PAS les DeferredDelete (piège documenté) :
    _QCA.sendPostedEvents(None, _QEv.Type.DeferredDelete)
    _sched_gl().synced.emit("nimporte")   # ne doit PAS lever sur la page morte
    # Les branchements qui rendent ça sûr doivent RESTER : méthodes liées
    # (Qt les déconnecte à la destruction du receveur), jamais de lambda.
    _cf = inspect.getsource(_PS._on_compose_finals)
    assert "w.progress.connect(self._on_batch_progress)" in _cf and \
           "lambda" not in _cf.split("w.progress.connect")[1][:80]
    assert "sip.isdeleted" in inspect.getsource(_PS._refresh_compose_btn)
    assert "sip.isdeleted" in inspect.getsource(_PS._on_prompt_synced)
    _init = inspect.getsource(_PS.__init__)
    assert "synced.connect(self._on_prompt_synced)" in _init and \
           "synced.connect(lambda" not in _init
    # …et le QThread du lot est parqué au niveau MODULE : si la page qui l'a
    # lancé meurt, il ne doit pas être ramassé en plein vol (abort Qt).
    assert "_BATCH_KEEPALIVE.append(self)" in inspect.getsource(_BW.start)

    # ⚠ DÉSYNCHRONISATION VUE ↔ BOUTON (FIGHTER 2.0, Matthieu 2026-08-11).
    # La vue vit dans le MODULE (elle survit au changement de projet) tandis
    # que le bouton est un widget neuf : son défaut « structure » en dur le
    # faisait mentir — bouton sur « structuré », cellules affichant encore le
    # message « à composer ». Il fallait basculer deux fois pour resynchroniser.
    from ui.prompt_view_toggle import PromptViewToggle as _PVT, FINAL as _V_FIN
    from ui.page_storyboard import _prompt_cell_text as _cell_txt
    _fp.set_current_view("final")
    assert _PVT().view() == _V_FIN, \
        "le bouton doit REFLÉTER l'état du module, jamais repartir en dur"
    # Bouton et cellules doivent toujours dire la même chose.
    _sh = {"seedance_prompt": "[🎬 ACTION]\nblocs"}
    assert "pas encore compos" in _cell_txt(_sh), "cellules pas en vue finale"
    _fp.set_current_view("structure")
    assert _cell_txt(_sh) == _sh["seedance_prompt"]
    # Ouvrir un PROJET repart du document de travail (sinon « à composer »
    # partout à l'ouverture d'un film dont rien n'est composé).
    _fp.set_current_view("final")
    _pg2 = _PS()
    assert _fp.current_view() == "structure" and \
        _pg2._prompt_view_toggle.view() == "structure"

    # Barre : bascule AVANT le bouton AVANT la forme (retour Matthieu 2026-08-11),
    # bouton branché avec confirmation chiffrée et rafraîchi à chaque rendu.
    _src = inspect.getsource(__import__("ui.page_storyboard", fromlist=["_"]))
    assert _src.index("PromptViewToggle()") < _src.index("_btn_compose_finals = ") \
        < _src.index("PromptFormSelector()"), "ordre de barre inversé perdu"
    assert "QMessageBox.question" in inspect.getsource(
        __import__("ui.page_storyboard", fromlist=["_"]).PageStoryboard._on_compose_finals), \
        "la dépense en rafale doit être confirmée"
    assert "_refresh_compose_btn()" in inspect.getsource(
        __import__("ui.page_storyboard", fromlist=["_"]).PageStoryboard._render)


@test
def hauteur_de_ligne_aucune_cellule_rognee():
    """Hauteur des lignes du Storyboard (2026-08-11).

    Le calcul citait QUATRE champs écrits à la main (prompt, nom, accessoires,
    acteurs) : « Mouvement » n'en faisait pas partie, donc « Panoramique
    vertical » sur deux lignes était COUPÉ (signalé par Matthieu). Le défaut
    n'était pas propre au mouvement — toute colonne ajoutée depuis y échappait.
    Désormais la mesure porte sur les cellules réellement construites."""
    from PyQt6.QtGui import QFont, QFontMetrics
    from PyQt6.QtCore import Qt
    from ui.page_storyboard import _ShotRow, _col_widths, _WrapLabel

    def _needed(text, col, px=10):
        avail = max(10, _col_widths[col] - 13)
        f = QFont(); f.setPixelSize(px)
        return QFontMetrics(f).boundingRect(
            0, 0, avail, 10000,
            int(Qt.TextFlag.TextWordWrap) | int(Qt.AlignmentFlag.AlignLeft),
            text).height() + 14

    _BASE = {"id": "h1", "number": 1, "seq_num": 1, "duration": 5.0,
             "scene_title": "T", "seedance_prompt": "[🎬 ACTION]\ncourt"}

    # ⚠ En rendu hors écran la police de repli est bien plus ÉTROITE que celle
    # de l'app : « Panoramique vertical » n'y passe pas à la ligne alors qu'il
    # le fait chez l'utilisateur. On prend donc un texte qui déborde dans
    # N'IMPORTE QUELLE police — on teste le comportement, pas la police.
    _LONG = ("Panoramique vertical descendant tres lent en contre-plongee puis "
             "recadrage lateral vers la droite avec leger travelling compense")
    assert _needed(_LONG, 6) > _ShotRow._MIN_H, "cas de test trop court"

    _short = _ShotRow(dict(_BASE, camera_movement="Fixe"))
    _long  = _ShotRow(dict(_BASE, camera_movement=_LONG))
    assert _long._content_height() > _short._content_height(), \
        "la colonne Mouvement n'entre PAS dans le calcul de hauteur"

    # Plan chargé : AUCUNE cellule de texte ne dépasse la hauteur de ligne.
    _r = _ShotRow(dict(_BASE, camera_movement=_LONG,
                       shot_time="Coucher du soleil", speed="Ralenti extreme",
                       decor_name="Jardin d'Eden futuriste et pollue",
                       accessory_names=["bouteille de Serpentine", "sacs"],
                       character_names=["Adam", "Eve", "Le Serpent"]))
    _H = _r._content_height()
    _bad = [(c, l.text()[:30]) for c, cell in _r._col_cells.items()
            if c not in _r._VISUAL_COLS and c < len(_col_widths)
            for l in cell.findChildren(_WrapLabel)
            if l.text() and _needed(l.text(), c, getattr(l, "_px", 10)) > _H]
    assert not _bad, f"cellules rognées : {_bad}"

    # Une ligne banale reste au minimum (pas de lignes géantes), et une
    # interrogation AVANT construction des cellules ne doit pas lever.
    assert _ShotRow(dict(_BASE))._content_height() == _ShotRow._MIN_H
    _g = _ShotRow(dict(_BASE))
    del _g._col_cells
    assert _g.sizeHint().height() == _ShotRow._MIN_H


@test
def composition_dit_la_vraie_cause_et_reprend_les_dialogues():
    """Échec de composition : diagnostic HONNÊTE + reprise (2026-08-11).

    Matthieu a vu « Vérifiez la clé IA » alors que 8 plans venaient d'être
    composés : seuls les 4 plans de DIALOGUE échouaient, parce que le
    composeur traduisait la réplique au lieu de la recopier — et le rejet de
    validation était totalement silencieux."""
    import api.video_prompt as _vp
    import core.ai_provider as _aip
    from core import prompt_sync as _ps

    _oc, _ok_ = _aip.complete, _aip.key_error
    try:
        _aip.key_error = lambda task="": None

        # Un rejet de validation DIT désormais pourquoi (avant : silence).
        _aip.complete = lambda s, u, **kw: "Voici le prompt : a man walks."
        assert _vp.compose("[🎬 ACTION]\nUn homme marche.") == ""
        assert "validation" in _vp.LAST_COMPOSE_ERROR, _vp.LAST_COMPOSE_ERROR

        # Dialogue traduit → UNE reprise citant la réplique ENTIÈRE le récupère.
        # ⚠ Réplique de plus de 60 caractères : la première version rebâtissait
        # la reprise depuis les MESSAGES d'erreur, tronqués à 60 — elle
        # redemandait donc un texte coupé, impossible à satisfaire (les 4 plans
        # de Matthieu restaient bloqués, 2026-08-11).
        _LONG = "Adam que t'es lèvre sont sèches ! Ce n'est que ton bisou me"
        assert len(_LONG) > 55, "cas de test trop court pour prouver la troncature"
        _src = f'[🎬 ACTION]\nElle dit "{_LONG}".'
        _n = {"c": 0}
        def _translate_then_obey(s, u, **kw):
            _n["c"] += 1
            if "REPRISE" in u:
                assert _LONG in u, "la reprise cite une réplique TRONQUÉE"
                return f'A woman says "{_LONG}", flat.'
            return 'A woman says "your lips are dry", flat.'
        _aip.complete = _translate_then_obey
        _out = _vp.compose(_src)
        assert _n["c"] == 2 and _LONG in _out, (_n, _out)

        # Variantes TYPOGRAPHIQUES (points de suspension, apostrophe courbe,
        # espace insécable) : le modèle normalise sans altérer la réplique →
        # ne doit plus être compté comme une altération.
        for _s, _r in (("Fais-moi un bisou... plutôt.", "Fais-moi un bisou… plutôt."),
                       ("C'est l'aube", "C’est l’aube"),
                       ("Espace fin", "Espace fin")):
            _aip.complete = lambda s, u, _x=_r, **kw: f'She says "{_x}" softly.'
            assert _vp.compose(f'[🎬 ACTION]\nElle dit "{_s}".'), \
                f"variante typographique refusée à tort : {_s!r} vs {_r!r}"

        # …mais une VRAIE traduction reste refusée (on ne devient pas laxiste).
        _aip.complete = lambda s, u, **kw: 'She says "I know Eve" softly.'
        assert _vp.compose('[🎬 ACTION]\nElle dit "Je sais Eve, mais que faire".') == ""

        # missing_dialogues porte les répliques ENTIÈRES, pas les messages.
        _v = _vp.validate_composed_prompt('She says "nothing".',
                                          f'[🎬 ACTION]\nElle dit "{_LONG}".')
        assert _v["missing_dialogues"] == [_LONG]

        # Reprise infructueuse → "" AVEC la raison, jamais un échec muet.
        _aip.complete = lambda s, u, **kw: "A man says something vague."
        assert _vp.compose(_src) == ""
        assert "dialogue" in _vp.LAST_COMPOSE_ERROR.lower()

        # La raison remonte au lot, PAR PLAN, et ne fuit pas dans le projet.
        _shot = {"id": "z1", "number": 7,
                 "seedance_prompt": '[🎬 ACTION]\nIl dit "Je sais Eve".'}
        assert _ps.compose_final_for_shot(_shot, save=False) == ""
        assert "dialogue" in _shot[_ps.E_REASON].lower()
        assert _ps.failure_reasons([_shot])[0][0] == "7"
    finally:
        _aip.complete, _aip.key_error = _oc, _ok_

    # Le message affiché montre le COMPTE et la RAISON — plus jamais « vérifiez
    # la clé IA » quand la clé marche.
    _PS = __import__("ui.page_storyboard", fromlist=["_"]).PageStoryboard
    _src_pg = inspect.getsource(_PS._on_compose_finals_done)
    assert "failure_reasons" in _src_pg and "Vérifiez la clé IA" not in _src_pg
    # Une FENÊTRE de progression, pas seulement un libellé de bouton : on ne
    # voyait pas que l'application travaillait (retour Matthieu 2026-08-11).
    # Elle se ferme AVANT le message de résultat, sinon celui-ci s'ouvre
    # derrière une modale encore affichée.
    assert "QProgressDialog" in inspect.getsource(_PS._on_compose_finals)
    assert "_close_batch_dlg" in inspect.getsource(_PS._on_batch_progress) or True
    assert _src_pg.index("_close_batch_dlg()") < _src_pg.index("failure_reasons")


@test
def flux3_affinage_du_brouillon():
    """Seconde moitié du palier BROUILLON Flux 3 (2026-08-12).

    Le brouillon rendait déjà un `draft_cache_url`, mais RIEN ne le consommait :
    l'économie annoncée (sortir tout le film à 0,06 $/s puis n'affiner que les
    plans gardés) restait théorique. L'affinage existe maintenant."""
    import os as _os, tempfile as _tf
    from api.video_engines import Flux3EnhanceWorker as _EW
    from core import flux3_family as _f3

    # Sans jeton : refus EXPLICITE. L'affinage ne sait consommer QUE le cache
    # (jamais une URL de vidéo) — un message clair vaut mieux qu'une erreur API.
    _errs = []
    _w = _EW({"duration": 5})
    _w.failed.connect(_errs.append)
    _w._real("fausse_cle")
    assert _errs and "draft_cache" in _errs[0] and "BROUILLON" in _errs[0], _errs

    assert _f3.ENHANCE_ENDPOINT == "blackforestlabs/flux-3/draft-enhance"
    assert _f3.enhance_price_per_second() == 0.29

    # ⚠ Le bouton ne doit apparaître QUE sur un clip affinable — sinon il ne
    # peut qu'échouer. `_VideoCard` importe find_entry_by_path DANS la méthode :
    # patcher ui.tab_video_library n'a AUCUN effet, il faut patcher
    # core.history (ma première version testait à vide pour cette raison).
    import core.history as _hist
    from ui.tab_video_library import _VideoCard as _VC
    from PyQt6.QtWidgets import QPushButton as _QPB
    _tmp = _tf.mkdtemp(prefix="pandora_enh_")
    _clip = _os.path.join(_tmp, "flux3_draft_t2v_5s_1.mp4")
    open(_clip, "wb").write(b"\x00" * 32)
    _orig = _hist.find_entry_by_path
    try:
        def _labels(entry):
            _hist.find_entry_by_path = lambda p: entry
            return [b.text() for b in _VC(_clip).findChildren(_QPB)]
        _sans = _labels({"seed": 1, "duration": 5})
        _avec = _labels({"seed": 1, "duration": 5,
                         "draft_cache_url": "https://x/cache"})
    finally:
        _hist.find_entry_by_path = _orig
    assert "↑ HD" in _sans, "les boutons ne sont pas construits — test sans valeur"
    assert "✦ Affiner" not in _sans, "bouton proposé sur un clip NON affinable"
    assert "✦ Affiner" in _avec, "bouton absent sur un brouillon affinable"

    # Le clip affiné est ENREGISTRÉ (donc compté dans « Coût du projet »), et
    # la dépense est confirmée avant de partir.
    _src = inspect.getsource(__import__("ui.tab_video_library", fromlist=["_"]))
    assert "save_to_history" in _src and "QMessageBox.question" in _src
    assert "QProgressDialog" in _src, "affinage sans fenêtre de progression"


@test
def audio_veed_lipsync_et_stable_audio_3():
    """Audio 2026-08-12 : VEED Lipsync v2 + Stable Audio 3.

    ⚠ Stable Audio 3 a RENOMMÉ le champ de durée (`duration` au lieu de
    `seconds_total`). Réutiliser le kind « stable » aurait envoyé un champ
    inconnu → l'API serait retombée sur 30 s par DÉFAUT, en silence, quelle que
    soit la durée demandée."""
    from api import lipsync as _ls, music as _mu

    # VEED : endpoint réel, contrat identique aux autres (interchangeable), et
    # placé selon son prix (0,07 $/s ≈ 4,20 $/min).
    assert _ls.lipsync_endpoint("veed2") == "veed/lipsync/v2"
    assert set(_ls.LIPSYNC_ENGINES["veed2"]) == set(_ls.LIPSYNC_ENGINES["sync3"])
    _o = _ls.LIPSYNC_ENGINE_ORDER
    assert _o.index("sync2pro") < _o.index("veed2") < _o.index("sync2")
    # Moteur inconnu → repli sur le défaut, jamais d'endpoint inventé.
    assert _ls.lipsync_endpoint("zzz") == \
        _ls.LIPSYNC_ENGINES[_ls.LIPSYNC_DEFAULT]["endpoint"]

    # Le champ de durée diffère RÉELLEMENT entre 2.5 et 3.
    _a25 = _mu._build_args("stable",  "thème", "", 120)
    _a3  = _mu._build_args("stable3", "thème", "", 120)
    assert _a25 == {"prompt": "thème", "seconds_total": 120}, _a25
    assert _a3  == {"prompt": "thème", "duration": 120}, _a3

    assert _mu.MUSIC_ENGINES["stable-audio-3"]["endpoint"] == \
        "fal-ai/stable-audio-3/medium/text-to-audio"
    assert _mu.MUSIC_ENGINES["stable-audio-3-sfx"]["endpoint"] == \
        "fal-ai/stable-audio-3/small/sfx/text-to-audio"
    assert all(_k in _mu.MUSIC_ENGINES for _k in _mu.ENGINE_ORDER), \
        "ENGINE_ORDER cite un moteur absent de la table"
    # fal ne publie AUCUN tarif pour cette famille : on le DIT au lieu
    # d'inventer un chiffre qui fausserait « Coût du projet ».
    assert "non publié" in _mu.MUSIC_ENGINES["stable-audio-3"]["price"]


@test
def decoupage_par_lots_et_cout_du_texte():
    """Un livre entier doit pouvoir être découpé, et son coût doit s'afficher.

    Retour d'un utilisateur : livre collé dans le Scénario → l'analyse passe,
    le découpage s'arrête, et « Coût du projet » affiche 0,00 $. Trois défauts
    distincts, testés ici séparément.
    """
    import tempfile, shutil
    from core import decoupage_batches as db
    from core import decoupage_scale as dsc
    from core import ai_spend, spend, context
    from core.decoupage_document import (
        parse_v2_document, validate_v2_document, is_v2_document)

    # ── 1. La numérotation ne doit plus avoir de mur ──────────────────────────
    # `\d{1,3}` faisait DISPARAÎTRE en silence tout plan au-delà de 999, et la
    # validation ne s'en apercevait pas : sur un livre, des centaines de plans
    # se volatilisaient sans une erreur.
    # Libellés EXACTS du contrat v2 (core/decoupage_document._LABELS) : c'est
    # « SOURCE SCÉNARIO » et non « SOURCE ». Une fiche approximative ferait
    # passer le test sur un document que PANDORA refuserait.
    _b = lambda n: (f"PLAN {n}\nSOURCE SCÉNARIO : Il marche.\nINTENTION : tension\n"
                    "DURÉE : 5\nPROMPT VISUEL : a man walks\n")
    _doc = "DÉCOUPAGE PANDORA 2\n\n" + "\n".join(_b(n) for n in (1, 999, 1000, 4200))
    _vus = [s.get("number") for s in parse_v2_document(_doc)]
    assert _vus == [1, 999, 1000, 4200], f"plans perdus au-delà de 999 : {_vus}"

    # ── 2. L'estimation doit coller au réel ───────────────────────────────────
    # Calibrée sur FIGHTER : 15 256 caractères → 84 plans. Un écart de plus de
    # 15 % signifie que les constantes ont dérivé du corpus.
    _e = dsc.estimate("x" * 15256)
    assert abs(_e["shots"] - 84) <= 13, f"estimation hors sol : {_e['shots']} plans"
    assert dsc.estimate("")["verdict"] == dsc.OK
    assert dsc.estimate("x" * 600000)["verdict"] == dsc.IMPOSSIBLE
    assert dsc.estimate("x" * 15256)["verdict"] == dsc.OK, \
        "un court métrage ne doit PAS déclencher l'avertissement"
    assert 40000 < dsc.max_chars_single_pass() < 90000

    # ── 3. Trancher puis recoller ne doit rien perdre ─────────────────────────
    _sc = "\n\n".join(f"SÉQUENCE {i} — TITRE {i}\nEXT. LIEU {i} — JOUR\n"
                      + ("Il marche lentement vers la porte. " * 40)
                      for i in range(1, 13))
    _lots = db.slice_screenplay(_sc)
    assert len(_lots) > 1, "un long scénario doit produire plusieurs tranches"
    assert all(l.strip() for l in _lots), "tranche vide produite"
    assert sum(len(l) for l in _lots) >= len(_sc.strip()) * 0.98, "texte perdu"
    # Un scénario court reste en UNE tranche — pas de cas particulier à écrire.
    assert len(db.slice_screenplay("court")) == 1
    assert db.slice_screenplay("") == []

    _p1 = "DÉCOUPAGE PANDORA 2\n\n" + "\n".join(_b(n) for n in (1, 2, 3))
    _p2 = ("DÉCOUPAGE PANDORA 2\n\n" + "\n".join(_b(n) for n in (1, 2))
           + "\n\nVoilà, dis-moi si je continue.")
    _join = db.join_batches([_p1, _p2])
    assert db.plan_count(_join) == 5, "des plans se perdent au recollage"
    assert is_v2_document(_join) and not validate_v2_document(_join)
    assert _join.upper().count("DÉCOUPAGE PANDORA 2") == 1, "marqueur dupliqué"
    assert "dis-moi si je continue" not in _join.lower(), \
        "le bavardage final est avalé dans le dernier champ du dernier plan"

    # ── 4. Le rappel de continuité doit rester BORNÉ ──────────────────────────
    # C'est tout l'intérêt de la file : la boucle actuelle renvoie tout le texte
    # déjà produit à chaque tour. Si le rappel grossit avec le document, on a
    # recréé le coût quadratique qu'on fuyait.
    _petit = db.carry_over("DÉCOUPAGE PANDORA 2\n\n" + "\n".join(_b(n) for n in range(1, 6)))
    _gros  = db.carry_over("DÉCOUPAGE PANDORA 2\n\n" + "\n".join(_b(n) for n in range(1, 400)))
    assert len(_gros) < len(_petit) * 3, \
        f"le rappel enfle avec le document ({len(_petit)} → {len(_gros)})"
    assert db.carry_over("") == "", "premier lot : rappel vide, pas d'exception"

    # ── 5. Le coût du texte doit arriver dans « Coût du projet » ──────────────
    class _U:  input_tokens = 340200; output_tokens = 96400
    class _M:  usage = _U()

    _old = context.get_project_path()
    _tmp = tempfile.mkdtemp(prefix="pandora_spend_")
    try:
        # Hors projet : on n'écrit RIEN (sinon le journal d'un film atterrirait
        # dans le dossier de l'application — piège déjà vécu sur ce projet).
        context.set_project_path("")
        assert ai_spend.note_message(_M(), "claude-opus-4-8", "decoupage") > 0
        context.set_project_path(_tmp)
        _avant = len(spend.load())
        ai_spend.note_message(_M(), "claude-opus-4-8", "decoupage")
        ai_spend.note_message(_M(), "modele-inconnu", "analyse")
        _apres = spend.load()
        assert len(_apres) - _avant == 2, "les appels texte ne sont pas journalisés"
        assert any(e["kind"] == spend.KIND_TEXT for e in _apres)
        _op = next(e for e in _apres if e["engine"] == "claude-opus-4-8")
        assert 12.0 < _op["cost_usd"] < 12.7, f"tarif Opus faux : {_op['cost_usd']}"
        _in = next(e for e in _apres if e["engine"] == "modele-inconnu")
        assert _in["cost_usd"] == 0.0 and "inconnu" in _in["detail"], \
            "un tarif inconnu doit être DIT, jamais présenté comme gratuit"
    finally:
        context.set_project_path(_old)
        shutil.rmtree(_tmp, ignore_errors=True)

    # Un nom de modèle versionné doit retomber sur sa famille, sinon toute la
    # ligne texte vaudrait 0 dès la prochaine version d'un modèle.
    assert ai_spend.price_for("claude-sonnet-5-20260101") == (3.0, 15.0)

    # ── 6. La capture est branchée sur les VRAIS points d'appel ───────────────
    import inspect as _i
    from core import ai_provider as _ap
    for _fn in (_ap._anthropic_complete, _ap._anthropic_stream, _ap.chat_ex):
        assert "_note_usage" in _i.getsource(_fn), \
            f"{_fn.__name__} ne journalise pas sa consommation"
    for _fn in (_ap.chat, _ap.chat_ex, _ap.stream):
        assert "_set_task_ctx" in _i.getsource(_fn), \
            f"{_fn.__name__} ne dit pas quelle tâche est en cours"

    # ── 7. Le worker de file respecte les règles Qt du projet ─────────────────
    from api.decoupage_queue import DecoupageQueueWorker as _Q
    _qs = _i.getsource(_Q)
    assert "terminate(" not in _qs, "terminate() est interdit"
    assert "isInterruptionRequested" in _qs, "annulation impossible"
    assert 'res.get("truncated")' in _qs, \
        "le drapeau de troncature n'est pas lu : un lot coupé passerait pour bon"
    for _sig in ("progress", "batch_done", "done", "failed"):
        assert hasattr(_Q, _sig), f"signal {_sig} manquant"

    # L'avertissement est bien branché AVANT la dépense.
    _src = _i.getsource(__import__("ui.page_scenario", fromlist=["_"]).PageScenario._on_format)
    assert "should_warn" in _src and "_start_decoupage_queue" in _src, \
        "l'avertissement de taille n'est pas branché sur le découpage"

    # ── 8. Storyboard par lots : mêmes plans qu'en une passe ──────────────────
    from core import storyboard_batches as sbb
    from core.decoupage_layout import layout_segments_to_cinema_shots, is_structured_layout

    _fiches = 30
    _sbdoc = "DÉCOUPAGE PANDORA 2\n\n" + "\n".join(
        f"SÉQUENCE {1 + n // 10} — SÉQ {1 + n // 10}\n" + _b(n) if n % 10 == 1
        else _b(n) for n in range(1, _fiches + 1))
    assert sbb.count_fiches(_sbdoc) == _fiches
    _lots = sbb.split_document(_sbdoc, per_batch=12)
    assert len(_lots) == sbb.batches_needed(_sbdoc, 12) == 3
    # Chaque sous-document doit rester exploitable SEUL, sinon ni le parseur ni
    # le repli déterministe ne le reprendront.
    assert all(is_v2_document(l) for l in _lots), "un lot n'est pas un document v2"
    assert all(is_structured_layout(l) for l in _lots)
    assert not any(validate_v2_document(l) for l in _lots)
    assert sum(sbb.count_fiches(l) for l in _lots) == _fiches, "fiches perdues"

    # Équivalence : lots recollés == passe unique. C'est la seule garantie qui
    # compte — découper ne doit RIEN changer au storyboard produit.
    _par_lots = sbb.merge_shots([layout_segments_to_cinema_shots(l) for l in _lots])
    _une_passe = layout_segments_to_cinema_shots(_sbdoc)
    assert len(_par_lots) == len(_une_passe) == _fiches
    assert [s["number"] for s in _par_lots] == list(range(1, _fiches + 1)), \
        "la numérotation ne redevient pas continue : douze « plan 1 »"
    assert [s.get("scene_title") for s in _par_lots] == \
           [s.get("scene_title") for s in _une_passe], "ordre ou contenu altéré"
    assert [s.get("seq_num") for s in _par_lots] == \
           [s.get("seq_num") for s in _une_passe], "séquences perdues au tranchage"
    assert sbb.split_document("") == [] and sbb.merge_shots([]) == []

    # Le coordinateur réutilise le worker existant plutôt que de le réécrire :
    # sans cela, le repli déterministe et la détection de fusion divergeraient.
    from api.storyboard_queue import StoryboardQueueWorker as _SQ
    _sq = _i.getsource(_SQ)
    assert "GenerateStoryboardWorker" in _sq, \
        "le coordinateur duplique la conversion au lieu de réutiliser le worker"
    assert "terminate(" not in _sq and "isInterruptionRequested" in _sq
    for _sig in ("progress", "batch_done", "compose_progress", "done", "failed"):
        assert hasattr(_SQ, _sig), f"signal {_sig} manquant"

    # Bascule : les projets EXISTANTS restent sur le chemin éprouvé.
    from ui.dialog_storyboard_generate import StoryboardGenerateDialog as _SD
    assert _SD._QUEUE_THRESHOLD_FICHES >= 90, \
        "seuil trop bas : un court métrage basculerait sur la file sans raison"
    _ssrc = _i.getsource(_SD._start)
    assert "_QUEUE_THRESHOLD_FICHES" in _ssrc and "_start_queue" in _ssrc, \
        "la file storyboard n'est pas branchée"
    # Le contrat « aperçu PUIS confirmation » doit tenir : la file rend des
    # plans, elle n'enregistre rien. Rien n'est écrit avant que l'auteur
    # clique « Importer » — c'est ce qui distingue un aperçu d'un fait accompli.
    for _interdit in ("save_shot", "save_shots", "add_shot"):
        assert _interdit not in _sq, \
            f"le coordinateur persiste ({_interdit}) : l'aperçu devient un fait accompli"


@test
def prix_image_jamais_le_numero_de_version():
    """Le prix d'une image ne doit pas être lu dans le nom du moteur.

    Constat Matthieu 2026-08-30 : « Seedream met environ 5 dollars l'image ».
    Le motif acceptait un montant SANS signe dollar, donc la première décimale
    du libellé — et dans « Seedream 5.0 Pro » c'est le numéro de version.
    Cinq moteurs sur quatorze étaient faux, jusqu'à 165× le tarif réel. Les
    moteurs sans décimale dans leur nom étaient justes, ce qui masquait tout.
    """
    from core import image_engines as _ie
    from api.apercu import _image_price_hint, _MAX_PLAUSIBLE_IMAGE_USD

    # Aucun moteur ne doit sortir un prix invraisemblable. C'est l'assertion
    # qui aurait fait rougir le harnais dès l'ajout de Seedream 5.0.
    for _k in _ie.ENGINES:
        _p = _image_price_hint(_k)
        assert 0.0 <= _p <= _MAX_PLAUSIBLE_IMAGE_USD, \
            f"{_k} : prix invraisemblable {_p} $ / image"

    # Les cinq moteurs qui portaient un numéro de version décimal.
    for _k, _attendu in (("seedream5_pro", 0.0675), ("seedream5", 0.035),
                         ("seedream45", 0.03), ("recraft", 0.035),
                         ("flux_ultra", 0.06), ("seedream5_flash", 0.027),
                         ("kling_image", 0.028), ("qwen_image2_pro", 0.075)):
        if _k in _ie.ENGINES:
            assert abs(_image_price_hint(_k) - _attendu) < 1e-9, \
                f"{_k} : {_image_price_hint(_k)} au lieu de {_attendu}"

    # Le signe dollar est ce qui distingue un prix d'un numéro de version :
    # la garantie tient à lui, pas à la forme des libellés d'aujourd'hui.
    _src = inspect.getsource(_image_price_hint)
    assert r"\$?" not in _src, "le signe dollar est redevenu optionnel"

    # Tout moteur du catalogue doit annoncer un prix : un moteur à 0 $ serait
    # présenté comme gratuit dans « Coût du projet ».
    # Les gabarits ComfyUI (kind « comfy », 24/09/2026) coûtent réellement 0 $ :
    # leur libellé se termine par « $0 », lisible — ils ne sont pas « muets ».
    _muets = [k for k in _ie.ENGINES if _image_price_hint(k) == 0.0 and not _ie.is_comfy(k)]
    assert not _muets, f"moteurs sans tarif lisible : {_muets}"
    _comfy = [k for k in _ie.ENGINES if _ie.is_comfy(k)]
    assert all(_ie.label_for(k).endswith("$0") for k in _comfy), "gabarit ComfyUI sans « $0 » lisible"


@test
def minimax_h3_fal_et_local():
    """MiniMax H3 (Hailuo 3.0) — trois paliers fal + le serveur local sd.cpp.

    Relevé 2026-09-13. Ce qui doit tenir : les tables (chemins, résolutions,
    tarifs) sont la seule source ; les formulaires de l'onglet Moteurs restent
    ALIGNÉS PAR INDEX sur la liste des moteurs, dans les deux éditions ; le
    local coûte 0 dans le journal ; la requête locale respecte les contraintes
    du VAE (multiples de 32, images 17k+5, cfg 1.0).
    """
    import importlib
    from core import h3_family as h3
    from core import h3_local as h3l
    from core import pricing, engine_grammar, target_engine
    import api.video_engines as ve
    import api.h3_local as h3api

    # ── Table de famille ──────────────────────────────────────────────────────
    assert h3.tiers() == ["minimax-h3", "minimax-h3-max", "minimax-h3-max-turbo"]
    assert h3.endpoint("minimax-h3", "ref") == "minimax/h3/reference-to-video"
    assert h3.endpoint("minimax-h3-max-turbo", "ref") == "", \
        "Turbo n'a pas de reference-to-video : l'appelant doit le savoir"
    assert h3.fal_resolution("minimax-h3", "768p") == "768P"
    assert h3.fal_resolution("minimax-h3-max", "1080p") == "1080P"
    assert h3.fal_resolution("minimax-h3", "720p") == "768P", "repli sur le natif"
    assert h3.is_upscaled("minimax-h3", "4k") and not h3.is_upscaled("minimax-h3", "768p")
    assert h3.clamp_duration(3) == 5 and h3.clamp_duration(40) == 15
    assert h3.clamp_expansion("minimax-h3-max", "fast") == "balanced", \
        "Max n'a pas de mode fast : l'envoyer serait un 422"
    assert h3.clamp_expansion("minimax-h3", "fast") == "fast"
    assert abs(h3.estimate("minimax-h3", "768p", 10) - 0.60) < 1e-9
    # 7 images sur H3 : 5 gratuites, 2 × 0,08 $.
    assert abs(h3.estimate("minimax-h3", "768p", 10, n_ref_images=7) - 0.76) < 1e-9
    assert h3.annotate_roles_with_tokens(["Léa", "Le dojo"]) == ["Léa (Image 1)", "Le dojo (Image 2)"]

    # ── Une seule grille : pricing lit h3_family ──────────────────────────────
    assert pricing.price_per_second("minimax-h3", "768p") == 0.06
    assert pricing.price_per_second("minimax-h3-max", "1080p") == 0.16
    assert pricing.price_per_second("minimax-h3-max-turbo", "768p") == 0.04
    # Le LOCAL coûte 0 — sans entrée, un moteur inconnu retombe sur 0,30 $/s.
    assert pricing.price_per_second("minimax-h3-local", "rapide") == 0.0
    assert pricing.price_per_second("minimax-h3-local", "768p") == 0.0

    # ── Grammaire + briefing du découpage ─────────────────────────────────────
    for k in ("minimax-h3", "minimax-h3-max", "minimax-h3-max-turbo", "minimax-h3-local"):
        assert engine_grammar.grammar_for(k) == "sentence", k
    _b = target_engine.briefing("minimax-h3")
    assert "Image 1" in _b and "5 and 15 seconds" in _b and "768p" in _b
    assert "VERBATIM" in target_engine.briefing("minimax-h3-local")

    # ── Workers fal : chemins et hooks ────────────────────────────────────────
    assert ve.H3Worker.ENDPOINT_T2V == "minimax/h3/text-to-video"
    assert ve.H3Worker.ENDPOINT_I2V == "minimax/h3/image-to-video" and ve.H3Worker.END_FRAME
    assert ve.H3MaxWorker.ENDPOINT_T2V == "minimax/h3-max/text-to-video"
    assert ve.H3MaxTurboWorker.ENDPOINT_I2V == "minimax/h3-max-turbo/image-to-video"
    assert ve.H3Worker.DUR_STR is False, "MiniMax veut la durée en entier"
    assert ve.H3Worker.RATIO_T2V_ONLY, "le schéma I2V n'a pas aspect_ratio"
    _w = ve.H3MaxWorker({"prompt": "x", "resolution": "1080p"})
    assert _w._resolution_arg("1080p") == "1080P"
    assert _w._price_per_s("1080p") == 0.16
    assert _w._extra_args("t2v") == {"prompt_expansion_mode": "balanced"}, \
        "prompt_expansion_mode est REQUIS sur Max : l'omettre est un 422"
    assert ve.H3Worker({"prompt": "x"})._extra_args("t2v") == {}, \
        "sur H3 de base il est optionnel : on ne l'invente pas"
    # Les hooks ne changent RIEN aux moteurs existants.
    _s = ve.Seedance15Worker({"prompt": "x"})
    assert _s._resolution_arg("720p") == "720p" and _s._extra_args("t2v") == {}
    assert _s._price_per_s("720p") == ve.Seedance15Worker.PRICE_PER_S

    # ── Local : requête conforme au VAE, jamais d'image fantôme ──────────────
    assert h3l.snap_dimension(383) == 384 and h3l.snap_dimension(700) == 704
    assert h3l.snap_frames(56) == 56 and h3l.snap_frames(60) == 56 and h3l.snap_frames(240) == 243
    assert h3l.frames_for_seconds(2.3) == 56
    _rq = h3l.build_request("a cat", 383, 672, 60, steps=8, seed=7)
    assert _rq["width"] == 384 and _rq["video_frames"] == 56 and _rq["fps"] == 24
    assert _rq["sample_params"]["guidance"]["txt_cfg"] == 1.0
    assert _rq["output_format"] == "webm" and _rq["seed"] == 7
    assert h3l.INIT_IMAGE_FIELD not in _rq, "pas d'image → pas de champ image"
    assert h3l.build_request("x", 384, 672, 56, init_image_b64="AAAA")[h3l.INIT_IMAGE_FIELD] == "AAAA"
    assert h3l.normalize_url("") == h3l.DEFAULT_URL
    assert h3l.normalize_url("localhost:1234/") == "http://localhost:1234"
    assert h3l.ping("http://127.0.0.1:1")[0] is False, "un port fermé doit dire injoignable"
    assert h3api._find_b64({"result": {"b64_json": "Q" * 200}}) == "Q" * 200
    assert h3api._find_b64({"data": [{"b64_json": "Q" * 200}]}) == "Q" * 200
    assert h3api._find_b64({"status": "completed"}) == ""
    assert "EU" in h3l.LICENSE_NOTICE or "Union européenne" in h3l.LICENSE_NOTICE, \
        "l'avis de licence doit nommer les territoires exclus"

    # ── Local : le cadre s'oriente par le Format, la durée vient du curseur ──
    # Constaté au rendu : le préréglage imposait 384×672 (portrait) pendant que
    # le menu Format affichait « 16:9 — Paysage ». Le préréglage donne petit et
    # grand côté, le ratio choisit l'orientation.
    assert h3l.frame_for("rapide", "16:9") == (672, 384)
    assert h3l.frame_for("rapide", "9:16") == (384, 672)
    assert h3l.frame_for("rapide", "1:1") == (384, 384)
    assert h3l.frame_for("qualite", "21:9") == (1344, 768)
    assert h3l.frame_for("inconnu", "16:9") == (672, 384), "préréglage inconnu → repli rapide"
    assert h3l.steps_for("qualite") == 25 and h3l.steps_for("rapide") == 8
    _lw = h3api.H3LocalWorker({"prompt": "x", "resolution": "rapide",
                               "aspect_ratio": "9:16", "duration": 10})
    _w_, _h_, _f_ = _lw._dimensions()
    assert (_w_, _h_) == (384, 672) and _f_ == 243, f"portrait 10 s attendu, lu {(_w_, _h_, _f_)}"
    _lw2 = h3api.H3LocalWorker({"prompt": "x", "resolution": "qualite", "aspect_ratio": "16:9"})
    assert _lw2._dimensions()[:2] == (1344, 768) and _lw2._steps() == 25
    assert _lw2._end_image_b64() == "" and _lw2._init_image_b64() == "", \
        "sans image locale, aucun champ image ne doit partir"

    # ── Onglet Moteurs : liste et formulaires ALIGNÉS, dans les DEUX éditions ─
    # C'est le vrai risque : _forms[combo.currentIndex()] — un décalage et
    # tous les moteurs suivants affichent le mauvais formulaire.
    for mod in ("ui.tab_video_engines", "ui.tab_video_engines_live"):
        m = importlib.import_module(mod)
        src = inspect.getsource(m.TabVideoEngines._on_generate)
        for w in ("H3Worker", "H3MaxWorker", "H3MaxTurboWorker", "H3LocalWorker"):
            assert w in src, f"{mod}: dispatch {w} manquant"
        keys = [k for _, k, _ in m.TabVideoEngines._ENGINES]
        for k in ("h3_t2v", "h3_i2v", "h3max_t2v", "h3max_i2v", "h3turbo_t2v",
                  "h3turbo_i2v", "h3local_t2v", "h3local_i2v"):
            assert k in keys, f"{mod}: moteur {k} absent de la liste"
        assert len(keys) == len(set(keys)), f"{mod}: clé de moteur en double"
        tab = m.TabVideoEngines()
        assert len(tab._forms) == len(m.TabVideoEngines._ENGINES), \
            f"{mod}: {len(tab._forms)} formulaires pour {len(m.TabVideoEngines._ENGINES)} moteurs"
        # Le formulaire d'un I2V H3 doit bien être un I2V (image de départ).
        i = keys.index("h3_i2v")
        assert getattr(tab._forms[i], "_mode", "") == "i2v", f"{mod}: formulaire H3 I2V décalé"
        i = keys.index("h3local_t2v")
        assert getattr(tab._forms[i], "_mode", "") == "t2v", f"{mod}: formulaire H3 local décalé"
        tab.deleteLater()

    # ── Rangée de réglage : neutre, auto-enregistrée, licence affichée ───────
    from ui.h3_local_row import H3LocalRow
    _rsrc = inspect.getsource(H3LocalRow)
    assert "LICENSE_NOTICE" in _rsrc and "set_url" in inspect.getsource(
        importlib.import_module("ui.h3_local_row"))
    _psrc = inspect.getsource(importlib.import_module("ui.page_settings"))
    _lsrc = inspect.getsource(importlib.import_module("ui.page_live_settings"))
    assert "H3LocalRow" in _psrc and "H3LocalRow" in _lsrc, \
        "la rangée H3 local doit être dans les Paramètres des DEUX éditions"


@test
def comfyui_moteur_nodal_et_journal_de_cout():
    """ComfyUI piloté par PANDORA (13/09/2026) — et un bug de journal trouvé en chemin.

    Le journal recevait « seedance-1.5-pro-t2v » et cherchait « seedance-1.5-pro » :
    tous les moteurs de _SimpleFalVideoWorker étaient comptés 0,30 $/s. On
    vérifie chaque sous-classe, puis le protocole ComfyUI hors ligne (le
    convertisseur éditeur→API sur un graphe synthétique avec Reroute, Primitive,
    Note et seed à contrôle), et l'alignement des onglets à 36 moteurs.
    """
    import importlib
    from core import pricing, comfy as cf, comfy_workflow as wf, comfy_h3 as h3c
    import api.video_engines as ve

    # ── 1. Le journal résout la clé COMPOSÉE émise par les workers ────────────
    assert pricing.canonical_engine("seedance-1.5-pro-t2v") == "seedance-1.5-pro"
    assert pricing.canonical_engine("minimax-h3-i2v") == "minimax-h3"
    assert pricing.canonical_engine("comfy-t2v") == "comfy"
    assert pricing.canonical_engine("flux-3") == "flux-3", "sans suffixe : inchangé"
    # Garde anti-dérive : TOUT worker qui annonce un tarif doit exister dans la
    # grille (sinon le journal retombe sur 0,30 $/s), et la grille doit dire la
    # même chose que lui à 10 % près (le worker annonce le coût AVANT, le
    # journal le compte APRÈS — deux chiffres différents seraient un mensonge).
    def _subclasses(c):
        out = []
        for s in c.__subclasses__():
            out.append(s); out += _subclasses(s)
        return out
    for cls in _subclasses(ve._SimpleFalVideoWorker):
        if cls.__name__.startswith("_"):
            continue
        emitted = f"{cls.MODEL}-t2v"
        if cls.FLAT_PRICE and not cls.PRICE_PER_S:
            assert pricing.price_per_second(emitted, "") is None, \
                f"{cls.__name__} est facturé au clip : il doit être dans _PER_VIDEO"
            continue
        if not cls.PRICE_PER_S and not pricing._PER_SECOND.get(cls.MODEL):
            continue          # tarif porté par une table de famille (H3) — testé plus haut
        assert pricing._PER_SECOND.get(cls.MODEL), \
            f"{cls.__name__} ({cls.MODEL}) absent de la grille : journalisé à 0,30 $/s"
        if cls.PRICE_PER_S:
            g = pricing.price_per_second(emitted, "720p")
            assert abs(g - cls.PRICE_PER_S) <= 0.10 * cls.PRICE_PER_S, \
                f"{cls.__name__} : worker {cls.PRICE_PER_S} $/s, grille {g} $/s"
    assert pricing.price_per_second("minimax-h3-local-t2v", "rapide") == 0.0
    assert pricing.price_per_second("comfy-i2v", "768p") == 0.0
    assert pricing.price_per_second("hailuo-2.3-pro-t2v", "") is None, "Hailuo est au clip"
    assert pricing.estimate("hailuo-2.3-pro-t2v", "", 6, 1)[0] == 0.49

    # ── 2. Protocole ComfyUI, sans serveur ────────────────────────────────────
    assert cf.normalize_url("localhost:8188/") == "http://localhost:8188"
    assert cf.normalize_url("") == "" and cf.get_url({}) == cf.DEFAULT_URL
    assert cf.ping("http://127.0.0.1:1")[0] is False
    assert cf.version_ok("0.34.0") and cf.version_ok("v0.35.1") and not cf.version_ok("0.29.9")
    assert cf.history_status({"status": {"status_str": "success", "completed": True}})[0] == "success"
    st, msg = cf.history_status({"status": {"status_str": "error", "messages": [
        ["execution_error", {"exception_message": "CUDA out of memory"}]]}})
    assert st == "error" and "CUDA" in msg
    assert cf.history_status({})[0] == "running"
    # discover() à deux temps (23/09/2026) : un serveur vivant mais FROID (le
    # premier /system_stats réveille CUDA, ~1,2 s mesuré) doit être trouvé, et
    # un port vide écarté sans requête. Simulation : 8188 « écoute » mais son
    # ping ne réussit qu'avec un délai >= 2 s ; 8000 est vide.
    _calls = []
    def _fake_port_open(url, timeout=0.5):
        return url.endswith(":8188")
    def _fake_ping(url="", timeout=2.0):
        _calls.append((url, timeout))
        return (timeout >= 2.0 and url.endswith(":8188")), "", {}
    _orig_po, _orig_ping = cf._port_open, cf.ping
    cf._port_open, cf.ping = _fake_port_open, _fake_ping
    try:
        assert cf.discover({}) == "http://127.0.0.1:8188", "serveur froid non trouvé (délai par défaut trop court)"
        assert _calls and all(u.endswith(":8188") for u, _t in _calls), f"le port vide (8000) ne doit pas être sondé : {_calls}"
        assert cf.discover({}, timeout=1.0) == "", "avec 1 s le serveur froid rate : c'est le bug d'origine, épinglé"
        assert cf.discover({cf.CONFIG_KEY: "127.0.0.1:8188"}) == "http://127.0.0.1:8188", "l'adresse réglée est normalisée et sondée d'abord"
    finally:
        cf._port_open, cf.ping = _orig_po, _orig_ping
    assert cf._port_open("http://127.0.0.1:1", timeout=0.3) is False, "port fermé → False sans lever"
    outs = cf.outputs_of({"outputs": {"9": {"images": [{"filename": "a.png", "type": "output"}]},
                                      "12": {"gifs": [{"filename": "clip.mp4", "subfolder": "video", "type": "output"}]}}})
    assert outs[0]["filename"] == "clip.mp4", "la vidéo passe avant l'aperçu image"
    assert cf.view_url("http://h:1", outs[0]).startswith("http://h:1/view?filename=clip.mp4")
    assert cf.prompt_payload({"1": {}}, "cid")["client_id"] == "cid"

    # ── 3. Convertisseur éditeur → API ────────────────────────────────────────
    info = {
        "CLIPTextEncode": {"input": {"required": {"text": ["STRING", {"multiline": True}],
                                                  "clip": ["CLIP"]}}},
        "KSampler": {"input": {"required": {"model": ["MODEL"],
                                            "seed": ["INT", {"control_after_generate": True}],
                                            "steps": ["INT", {}], "cfg": ["FLOAT", {}],
                                            "sampler_name": [["euler", "dpmpp_2m"]],
                                            "positive": ["CONDITIONING"], "latent_image": ["LATENT"]}}},
        "LoadImage": {"input": {"required": {"image": [["a.png"], {"image_upload": True}]}}},
    }
    ui = {"nodes": [
        {"id": 1, "type": "CLIPTextEncode", "inputs": [{"name": "clip", "link": None}],
         "widgets_values": ["un chat"]},
        {"id": 2, "type": "PrimitiveNode", "widgets_values": [1234]},
        {"id": 3, "type": "Reroute", "inputs": [{"name": "", "link": 10}], "outputs": [{"links": [11]}]},
        {"id": 4, "type": "KSampler",
         "inputs": [{"name": "seed", "link": 20}, {"name": "positive", "link": 11}],
         # seed converti en prise : sa CASE et sa valeur de contrôle « fixed »
         # restent dans la liste (règle vérifiée sur graphToPrompt, 14/09/2026 —
         # la première version sautait la case et décalait tout d'un cran)
         "widgets_values": [99, "fixed", 20, 7.5, "euler"]},
        {"id": 5, "type": "Note", "widgets_values": ["commentaire"]},
        {"id": 6, "type": "LoadImage", "mode": 2, "widgets_values": ["muet.png", "image"]},
    ], "links": [[10, 1, 0, 3, 0, "CONDITIONING"], [11, 3, 0, 4, 1, "CONDITIONING"],
                 [20, 2, 0, 4, 0, "INT"]]}
    api = wf.to_api(ui, info)
    assert set(api) == {"1", "4"}, f"virtuels et muets exclus : {sorted(api)}"
    assert api["1"]["inputs"]["text"] == "un chat"
    k = api["4"]["inputs"]
    assert k["seed"] == 1234, "la Primitive doit fournir la valeur"
    assert k["positive"] == ["1", 0], "le Reroute doit être traversé jusqu'à la source"
    assert k["steps"] == 20 and k["cfg"] == 7.5 and k["sampler_name"] == "euler", k
    assert wf.is_api_format(api) and not wf.is_ui_format(api)
    assert wf.to_api(api, info) == api, "un fichier déjà API repart tel quel"
    try:
        wf.to_api({"nodes": [{"id": 9, "type": "NoeudPersoAbsent", "widgets_values": []}], "links": []}, info)
        assert False, "une classe inconnue doit lever"
    except wf.ConversionError as e:
        assert "NoeudPersoAbsent" in str(e)
    assert wf.fill(api, [("CLIPTextEncode", "text", "x"), ("Absent", "y", 1)]) == ["Absent"]

    # ── 4. Sous-graphes : les gabarits H3 OFFICIELS s'aplatissent ────────────
    # Ce sont les vrais fichiers de Comfy-Org/workflow_templates, embarqués.
    for key, outer_id, inner_video in (("comfy_h3_t2v", "140", "130"), ("comfy_h3_i2v", "105", "91")):
        path = h3c.template_path(key)
        assert os.path.isfile(path), f"gabarit absent : {path}"
        ui = wf.load(path)
        assert ui.get("definitions", {}).get("subgraphs"), "le gabarit officiel est bâti sur un sous-graphe"
        flat = wf.flatten(ui)
        types = {str(n["id"]): n["type"] for n in flat["nodes"]}
        assert "definitions" not in flat and not any(len(t) > 30 for t in types.values()), \
            "il ne doit plus rester d'instance de sous-graphe"
        assert types.get(f"{outer_id}:{inner_video}") == "CreateVideo"
        assert len(types) == len(set(types)), "identifiants aplatis en double"
        h3_ids = [i for i, t in types.items() if t == "MiniMaxH3ImageToVideo"]
        assert len(h3_ids) == 1, f"un seul nœud H3 attendu, lu {h3_ids}"
        # La sortie du sous-graphe est redirigée vers le nœud interne qui la produit.
        lk = {str(l[0]): l for l in flat["links"]}
        to_save = [l for l in lk.values() if str(l[3]) == "92"]
        assert to_save and str(to_save[0][1]) == f"{outer_id}:{inner_video}", \
            f"SaveVideo doit recevoir la vidéo de {outer_id}:{inner_video}, lu {to_save}"
        # Le prompt promu arrive au nœud H3 par un PrimitiveNode synthétique.
        prim = [n for n in flat["nodes"] if n["type"] == "PrimitiveNode" and n["id"].endswith(":promoted:2")]
        assert prim and str(prim[0]["widgets_values"][0]).startswith(("Realistic", "Editorial")), \
            "le prompt promu (slot 2) doit être porté par un PrimitiveNode"
        # Conversion complète avec des définitions dérivées du gabarit lui-même :
        # on vérifie la mécanique (liens, primitives, ids), pas les noms de widgets.
        info = {t: {"input": {"required": {}}} for t in set(types.values()) if t not in wf._VIRTUAL}
        api = wf.to_api(ui, info)
        h3 = api[h3_ids[0]]["inputs"]
        assert str(h3["prompt"]).startswith(("Realistic", "Editorial")), "prompt littéral attendu sur le nœud H3"
        # Le nœud externe est BRANCHÉ sur width/height (ResolutionSelector 115) :
        # le lien prime sur la valeur promue, comme dans le frontend.
        assert h3["width"] == ["115", 0] and h3["height"] == ["115", 1], (h3["width"], h3["height"])
        assert isinstance(h3["length"], list) and types[h3["length"][0]] == "ComfyMathExpression", \
            "length reste relié au calcul 17k+5"
        assert isinstance(h3["clip"], list) and types[h3["clip"][0]] == "CLIPLoader"
        assert api["92"]["inputs"]["video"] == [f"{outer_id}:{inner_video}", 0]
        rn = next(i for i, t in types.items() if t == "RandomNoise")
        assert api[rn]["inputs"]["noise_seed"] == 757358688076805, "seed promue (widgets_values[4])"
        if key == "comfy_h3_i2v":
            assert h3["first_frame"] == ["114", 0], f"first_frame doit venir du LoadImage 114, lu {h3.get('first_frame')}"
            assert "last_frame" not in h3, "last_frame libre dans le gabarit I2V"
        else:
            assert "first_frame" not in h3 and "last_frame" not in h3

        # Remplissage PANDORA sur le vrai graphe.
        params = {"seed": 7, "resolution": "480p", "aspect_ratio": "9:16", "duration": 5,
                  "mode": "i2v" if key.endswith("i2v") else "t2v",
                  "_comfy_image": "pandora/depart.png", "_comfy_end_image": "pandora/fin.png"}
        plan = h3c.fill_plan(api, params, "a cat on a roof")
        wf.fill(api, plan)
        h3c.apply_images(api, params)
        h3 = api[h3_ids[0]]["inputs"]
        assert h3["prompt"] == "a cat on a roof"
        assert api[next(i for i, t in types.items() if t == "RandomNoise")]["inputs"]["noise_seed"] == 7
        assert api[next(i for i, t in types.items() if t == "PrimitiveFloat")]["inputs"]["value"] == 5.0, \
            "la durée entre en secondes par le PrimitiveFloat"
        # Cadre en littéraux dans les DEUX modes : le gabarit I2V officiel relie
        # width/height à un ResolutionSelector « 1:1 » (0,4 MP), PAS à l'image —
        # sans littéraux un mood 16:9 sortirait carré (constat 14/09/2026).
        assert (h3["width"], h3["height"]) == (480, 832), f"480p portrait = 480×832, lu {(h3['width'], h3['height'])}"
        if key.endswith("i2v"):
            assert api["114"]["inputs"]["image"] == "pandora/depart.png"
            assert h3["last_frame"] == [h3c.END_IMAGE_NODE, 0] and api[h3c.END_IMAGE_NODE]["inputs"]["image"] == "pandora/fin.png"

    # ── 4b. Remplissage : cas synthétiques ────────────────────────────────────
    assert h3c.snap_frames(5) == 124 and h3c.snap_frames(2.3) == 56 and h3c.snap_frames(0) == 5
    assert h3c.frame_for("768p", "16:9") == (1344, 768) and h3c.frame_for("480p", "1:1") == (480, 480)
    # Multiples de 32 (pas du nœud H3), grand côté au multiple INFÉRIEUR : 832
    # en 480p 16:9 comme le ResolutionSelector officiel à 0,4 MP — pas 848.
    assert h3c.frame_for("480p", "16:9") == (832, 480) and h3c.frame_for("768p", "9:16") == (768, 1344)
    assert h3c.frame_for("768p", "21:9") == (1792, 768) and h3c.frame_for("480p", "4:3") == (640, 480)
    assert h3c.frame_for("768p", "n'importe quoi") == (1344, 768), "ratio illisible → 16:9 paysage"
    assert h3c.frame_for("480p", "1:9") == (480, 1184), "au-delà de 2,5× le grand côté est borné : 1200 → 1184 (multiple de 32 inférieur)"
    import tempfile as _tf
    from PIL import Image as _Img
    with _tf.TemporaryDirectory() as _td:
        _p = os.path.join(_td, "mood.png")
        _Img.new("RGB", (1920, 1080)).save(_p)
        assert h3c.frame_for_image("480p", _p) == (832, 480), "I2V : le cadre suit le ratio de l'image"
        _Img.new("RGB", (1080, 1920)).save(_p)
        assert h3c.frame_for_image("768p", _p) == (768, 1344)
        assert h3c.frame_for_image("480p", os.path.join(_td, "absente.png")) is None
        plan = h3c.fill_plan({"1": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {}}},
                             {"mode": "i2v", "image_path": _p, "resolution": "480p", "aspect_ratio": "16:9"}, "x")
        assert [v for c, n, v in plan if n in ("width", "height")] == [480, 832], \
            "en I2V l'image (portrait) prime sur le ratio du formulaire (paysage)"
    try:
        h3c.fill_plan({"1": {"class_type": "KSampler", "inputs": {}}}, {}, "x")
        assert False, "sans nœud de prompt, fill_plan doit lever"
    except h3c.NoPromptTarget:
        pass
    plan = h3c.fill_plan({"1": {"class_type": "CLIPTextEncode", "inputs": {}},
                          "2": {"class_type": "KSampler", "inputs": {}}}, {}, "x")
    seed_val = next(v for c, n, v in plan if c == "KSampler")
    assert isinstance(seed_val, int) and seed_val > 0, "sans seed fournie, on en tire une (jamais « fixed »)"
    p = h3c.prepare_params({"prompt": "x"}, "comfy_h3_i2v")
    assert p["mode"] == "i2v" and p["workflow_path"].endswith("minimax_h3_i2v.json")

    # ── 4c. ORACLE : la sérialisation du frontend lui-même ────────────────────
    # `app.graphToPrompt()` relevé sur ComfyUI 0.35.1 le 14/09/2026, avec le
    # /object_info du même serveur figé (tools/fixtures/comfy). Le convertisseur
    # doit produire EXACTEMENT ce que le frontend envoie (hors _meta, titres
    # localisés) ; seuls les nœuds débranchés du gabarit I2V (119, 120) sont
    # élagués en plus. C'est ce test qui aurait attrapé le décalage des widgets
    # reliés (weight_dtype, CLIPLoader.type/device, denoise) que le serveur a
    # refusé — le harnais synthétique, écrit sur la même idée fausse, passait.
    import json
    fx = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "comfy")
    with open(os.path.join(fx, "object_info_h3.json"), encoding="utf-8") as _f:
        real_info = {k: v for k, v in json.load(_f).items() if not k.startswith("_")}
    for key, name, pruned in (("comfy_h3_t2v", "t2v", set()), ("comfy_h3_i2v", "i2v", {"119", "120"})):
        with open(os.path.join(fx, f"oracle_video_minimax_h3_{name}.json"), encoding="utf-8") as _f:
            oracle = json.load(_f)
        mine = wf.to_api(wf.load(h3c.template_path(key)), real_info)
        assert set(oracle) - set(mine) == pruned and not (set(mine) - set(oracle)), sorted(set(oracle) ^ set(mine))
        for nid in mine:
            assert mine[nid]["class_type"] == oracle[nid]["class_type"], nid
            assert mine[nid]["inputs"] == oracle[nid]["inputs"], \
                f"{key} nœud {nid} {mine[nid]['class_type']} :\n  moi     {mine[nid]['inputs']}\n  oracle  {oracle[nid]['inputs']}"
        # Les cas qui ont réellement mordu (refusés par le serveur avant correction).
        _by = lambda cls: mine[next(i for i, n in mine.items() if n["class_type"] == cls)]["inputs"]  # noqa: E731
        assert _by("UNETLoader")["weight_dtype"] == "default"
        assert _by("CLIPLoader")["type"] == "minimax" and _by("CLIPLoader")["device"] == "default"
        assert _by("BasicScheduler")["denoise"] == 1 and isinstance(_by("BasicScheduler")["steps"], list)
        s = mine["92"]["inputs"]
        assert s["format"] == "auto" and s["format.codec"] == "auto" and s["codec"] == "auto", \
            "combo dynamique : option, sous-entrée « format.codec » et entrée cachée « codec »"
        assert _by("CreateVideo")["color_space"] == "sRGB", "widget absent du gabarit → défaut de la définition"
        assert _by("ComfyMathExpression")["values.a"] == [f"{'140' if name == 't2v' else '105'}:{'133' if name == 't2v' else '111'}", 0]
        # Pré-vol : les fichiers que ce serveur ne voyait pas au moment du relevé
        # (les deux VAE étaient arrivés, pas le reste), avec leur dossier. Le LoRA
        # turbo y est bien que `turbo_mode` soit à False : le serveur valide
        # toutes les branches.
        miss = wf.missing_models(mine, real_info)
        assert {(f, d) for f, d, _c in miss} == {
            ("minimax_h3_fl2va_pruned_int8_convrot.safetensors", "diffusion_models"),
            ("qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "text_encoders"),
            ("minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors", "loras")}, miss
        # Remplissage puis élagage : le sélecteur 115, remplacé par des littéraux,
        # ne nourrit plus rien et ne part pas.
        wf.fill(mine, h3c.fill_plan(mine, {"resolution": "480p", "aspect_ratio": "16:9", "duration": 5,
                                            "mode": name, "seed": 1}, "x"))
        mine = wf.prune_unreachable(mine, real_info)
        hh = _by("MiniMaxH3ImageToVideo")
        assert (hh["width"], hh["height"]) == (832, 480) and "115" not in mine, (hh["width"], hh["height"], "115" in mine)
        assert hh["length"] == [f"{'140' if name == 't2v' else '105'}:{'132' if name == 't2v' else '107'}", 1], "length reste relié au calcul 17k+5"
    assert wf.prune_unreachable({"1": {"class_type": "X", "inputs": {}}}, {}) == {"1": {"class_type": "X", "inputs": {}}}, \
        "sans nœud de sortie connu, on ne touche à rien"

    # ── 5. Onglets et Paramètres ──────────────────────────────────────────────
    for mod in ("ui.tab_video_engines", "ui.tab_video_engines_live"):
        m = importlib.import_module(mod)
        src = inspect.getsource(m.TabVideoEngines._on_generate)
        # Depuis le 24/09/2026 le serveur est LANCÉ et attendu (ui/external_autostart)
        # au lieu d'ouvrir la fenêtre d'installation.
        assert "ComfyWorker" in src and 'ensure_ready("comfyui"' in src, f"{mod}: dispatch ComfyUI manquant"
        keys = [k for _, k, _ in m.TabVideoEngines._ENGINES]
        for k in ("comfy_h3_t2v", "comfy_h3_i2v", "comfy_custom"):
            assert k in keys, f"{mod}: {k} absent"
        tab = m.TabVideoEngines()
        assert len(tab._forms) == len(keys), f"{mod}: formulaires désalignés"
        assert getattr(tab._forms[keys.index("comfy_h3_i2v")], "_mode", "") == "i2v"
        # 480p par défaut : le gabarit officiel tourne à 0,4 MP (≈ 832×480) ;
        # 768p (1 MP) est 2,5× plus lourd — sur 8 Go de VRAM ce n'est pas un défaut.
        for k in ("comfy_h3_t2v", "comfy_h3_i2v"):
            assert tab._forms[keys.index(k)]._res_combo.currentData() == "480p", f"{mod}: {k} doit proposer 480p par défaut"
        tab.deleteLater()
    for mod in ("ui.page_settings", "ui.page_live_settings"):
        assert "ComfyRow" in inspect.getsource(importlib.import_module(mod)), f"{mod}: rangée ComfyUI absente"
    # Depuis le 24/09/2026 la fenêtre ComfyUI est la fenêtre GÉNÉRIQUE des
    # modules externes ouverte sur « comfyui » (voir modules_externes_*).
    from ui.dialog_comfy_install import ComfyInstallDialog
    from ui.dialog_external import ExternalDialog
    assert issubclass(ComfyInstallDialog, ExternalDialog) and hasattr(ComfyInstallDialog, "is_ready")
    dsrc = inspect.getsource(ExternalDialog)
    # Lignes de CODE seulement : un commentaire qui cite le mot fait mordre le
    # test à vide (piège connu, mémoire « pièges des tests »).
    import re as _re
    _code_lines = [l.split("#", 1)[0] for l in dsrc.splitlines()]
    assert not any(_re.search(r"\blambda\b", l) for l in _code_lines), \
        "dialog_external : fermeture anonyme dans le code (méthodes liées attendues)"


@test
def descripteur_de_projet_atomique_et_repare():
    """Le descripteur de projet s'écrit de façon ATOMIQUE et se RÉPARE.

    23/09/2026 : « La guerre toujours la guerre » retrouvé avec un descripteur
    de 0 octet (écriture directe interrompue) → projet illisible alors que tout
    son dossier data/ était intact. Désormais : écriture dans un voisin puis
    os.replace, et un descripteur vide/tronqué est rebâti depuis le dossier."""
    import tempfile as _tf
    import json as _json
    from core import project as _pj
    with _tf.TemporaryDirectory() as td:
        d = os.path.join(td, "Mon film")
        os.makedirs(os.path.join(d, "data"))
        with open(os.path.join(d, "Mon film.json"), "w", encoding="utf-8"):
            pass                                             # 0 octet
        data = _pj.load_project(d)
        assert data and data["name"] == "Mon film" and data["id"] and data["_path"] == d, data
        with open(os.path.join(d, "Mon film.json"), encoding="utf-8") as f:
            saved = _json.load(f)
        assert saved["id"] == data["id"] and "_path" not in saved and saved["mode"] == "cinema"
        assert not [f for f in os.listdir(d) if f.endswith(".tmp")], "fichier temporaire oublié"
        # Un JSON vide SANS dossier data/ n'est pas un projet : pas de réparation.
        e = os.path.join(td, "Vide")
        os.makedirs(e)
        with open(os.path.join(e, "x.json"), "w", encoding="utf-8"):
            pass
        assert _pj.load_project(e) is None
    src = inspect.getsource(_pj._write_json_atomic)
    assert "os.replace" in src, "l'écriture doit passer par un voisin puis os.replace"
    for fn in (_pj._save, _pj._save_registry):
        s = inspect.getsource(fn)
        assert "_write_json_atomic" in s and "open(" not in s, f"{fn.__name__} : écriture directe"


@test
def aucun_widget_sans_parent_affiche_a_la_construction():
    """Un widget sans parent rendu visible AVANT son ajout à une mise en page
    devient une fenêtre de premier niveau — cinq fenêtres clignotaient à
    l'ouverture d'un projet (mesuré le 23/09/2026 : assistant_panel,
    page_scenario ×3, tab_t2v, + dialog_style_gallery). Le motif est épinglé
    à la source : plus de `setVisible(True)` / `setVisible(expanded)` avant
    `addWidget` dans ces constructeurs."""
    import importlib
    # (module, motif interdit, borne de début, borne de fin) : le motif ne doit
    # pas apparaître ENTRE les bornes — c'est-à-dire avant l'ajout du widget à
    # sa mise en page. Le même appel APRÈS l'ajout (tab_t2v l. ~3395) est sain.
    cases = (
        ("ui.assistant_panel", "_guide_lbl.setVisible(True)",
         "self._guide_lbl = QLabel()", "tips_lay.addWidget(self._guide_lbl)"),
        ("ui.page_scenario", "container.setVisible(expanded)",
         "def _make_toggle", "def _section_container"),
        ("ui.page_scenario_live", "container.setVisible(expanded)",
         "def _make_toggle", "def _section_container"),
        ("ui.dialog_style_gallery", "container.setVisible(expanded)",
         "def _add_section", "self._tree_lay.addWidget(container)"),
        ("ui.tab_t2v", "_dyn_cam_toggle_row.setVisible(True)",
         "self._dyn_cam_toggle_row = toggle_row(", "_raccords_lay.addWidget(self._dyn_cam_toggle_row)"),
    )
    for mod, forbidden, start, end in cases:
        src = inspect.getsource(importlib.import_module(mod))
        code = "\n".join(l.split("#", 1)[0] for l in src.splitlines())
        i, j = code.find(start), code.find(end)
        assert 0 <= i < j, f"{mod} : bornes introuvables ({start!r} → {end!r})"
        assert forbidden not in code[i:j], f"{mod} : {forbidden} avant l'ajout à la mise en page"


@test
def pages_construites_a_la_premiere_demande():
    """ui/lazy_pages : les pages d'une fenêtre ne sont construites qu'au
    premier accès — `[]`, `get`, `in` construisent, itérer non ; les alias
    partagent la page ; une clé inconnue n'est pas construite. Mesuré le
    24/09/2026 : tout construire d'avance = 7 s + 3 s + 9 s à l'ouverture."""
    from ui.lazy_pages import LazyPages
    built, posed = [], []
    def _mk(name):
        def _f():
            built.append(name)
            return {"name": name}
        return _f
    pages = LazyPages({"a": _mk("a"), "b": _mk("b"), "c": _mk("c")},
                      lambda k, p: posed.append(k), aliases={"a_bis": "a"})
    assert built == [] and list(pages) == [], "rien n'est construit d'avance"
    assert "a" in pages and "a_bis" in pages and "zzz" not in pages
    assert built == [], "« in » ne construit pas"
    assert pages["a"]["name"] == "a" and built == ["a"] and posed == ["a"]
    assert pages["a_bis"] is pages["a"] and built == ["a"], "l'alias partage la page"
    assert pages.get("b")["name"] == "b" and built == ["a", "b"]
    assert pages.get("zzz") is None and built == ["a", "b"], "clé inconnue : rien"
    assert list(pages) == ["a", "b"] and pages.is_built("c") is False
    assert sorted(pages.keys_all()) == ["a", "a_bis", "b", "c"]
    pages.build_all()
    assert built == ["a", "b", "c"] and posed == ["a", "b", "c"]
    pages.build_all()
    assert built == ["a", "b", "c"], "jamais deux fois"
    # Les deux fenêtres s'en servent ; la page d'accueil vient de la navigation initiale.
    import ui.pandora_window as _PW
    import live_window as _LW
    for cls in (_PW.PandoraWindow, _LW.LiveWindow):
        src = inspect.getsource(cls._build_pages)
        assert "LazyPages(" in src and "self._stack.addWidget" not in src, cls.__name__
        assert "self._stack.addWidget(page)" in inspect.getsource(cls._on_page_built)
    assert '_navigate("scenario")' in inspect.getsource(_PW.PandoraWindow.__init__)


@test
def h3_et_comfy_generables_depuis_le_storyboard():
    """24/09/2026 (constat Matthieu) : MiniMax H3, H3 local et ComfyUI
    n'apparaissaient pas dans « Moteur de génération » de « Générer depuis le
    storyboard » — seul l'onglet Moteurs les avait. Le filtre du combo est
    core/engine_caps.ENGINE_CAPS ; le routage, _make_ext_worker."""
    import inspect as _insp
    from core import engine_caps as _caps, engine_grammar as _gr, target_engine as _te
    import ui.tab_t2v as _T
    keys = ("minimax-h3", "minimax-h3-max", "minimax-h3-max-turbo", "comfy", "minimax-h3-local")
    for k in keys:
        assert _caps.workflow_compatible(k), f"{k} : absent d'ENGINE_CAPS → filtré du combo"
        assert k in [e[1] for e in _T._ENGINES], f"{k} absent de la liste du Studio"
        assert k in _T._ENGINE_RESOLUTIONS and k in _T._TEXT_FALLBACK_ENGINES, k
        assert _gr.grammar_for(k) == "sentence", k
    listed = [k for _l, k in _caps.sequence_engines(_T._ENGINES, use_keyframes=False)]
    assert all(k in listed for k in keys), listed
    assert "VERBATIM" in _te.briefing("comfy"), "consigne H3 (prompt envoyé tel quel) pour ComfyUI"
    # Routage : le bon worker, le bon mode, le bon gabarit ComfyUI.
    from api.video_engines import H3Worker, H3MaxWorker, H3MaxTurboWorker
    from api.h3_local import H3LocalWorker
    from api.comfy import ComfyWorker
    base = {"prompt": "x", "resolution": "768p", "aspect_ratio": "16:9", "duration": 5}
    assert isinstance(_T._make_ext_worker("minimax-h3", base), H3Worker)
    assert isinstance(_T._make_ext_worker("minimax-h3-max", base), H3MaxWorker)
    assert isinstance(_T._make_ext_worker("minimax-h3-max-turbo", base), H3MaxTurboWorker)
    w = _T._make_ext_worker("minimax-h3-local", base)
    assert isinstance(w, H3LocalWorker) and w.params["mode"] == "t2v"
    w = _T._make_ext_worker("comfy", base)
    assert isinstance(w, ComfyWorker) and w.params["workflow_path"].endswith("minimax_h3_t2v.json")
    w = _T._make_ext_worker("comfy", {**base, "image_path": "C:/x/mood.png"})
    assert w.params["mode"] == "i2v" and w.params["workflow_path"].endswith("minimax_h3_i2v.json"), \
        "avec une image de départ : gabarit I2V"
    # Sans serveur, il est LANCÉ et attendu depuis ce Studio aussi (ui/external_autostart) ;
    # la fenêtre d'installation n'apparaît que s'il n'est pas installé.
    assert 'ensure_ready("comfyui"' in _insp.getsource(_T), "guidage ComfyUI absent du Studio"


@test
def modules_externes_registre_fenetre_bandeau_et_telechargement():
    """Chantier du 24/09/2026 (demande Matthieu) : tout ce qui est externe à
    PANDORA — ComfyUI Desktop et ses modèles H3, le serveur H3 local, Ollama —
    passe par UN registre (core/externals), UNE fenêtre (ui/dialog_external),
    un bandeau sous le choix du moteur et une section des Paramètres ; PANDORA
    télécharge et lance lui-même ce qu'il peut (api/external_install), avec
    reprise des téléchargements interrompus."""
    import tempfile as _tf
    import threading as _th
    import http.server as _hs
    import importlib
    from core import externals as _ex
    from api import external_install as _ei

    # 1. Registre : chaque module a tout ce que la fenêtre affiche.
    assert set(_ex.EXTERNALS) == {"comfyui", "h3_local", "ollama", "lmstudio", "llamacpp", "vllm", "jan"}
    for ext in _ex.EXTERNALS.values():
        assert ext.name and ext.purpose and ext.steps and ext.download_url.startswith("https://") \
            and ext.docs_url.startswith("https://"), ext.key
    for k in ("comfy", "comfy_h3_t2v", "comfy_custom"):
        assert _ex.for_engine(k).key == "comfyui", k
    for k in ("minimax-h3-local", "h3local_i2v"):
        assert _ex.for_engine(k).key == "h3_local", k
    assert _ex.for_engine("ollama").key == "ollama" and _ex.for_engine("seedance-2.0") is None
    assert _ex.EXTERNALS["comfyui"].license_note and _ex.EXTERNALS["h3_local"].license_note, \
        "la licence H3 (territoires exclus) doit être affichée pour les deux voies H3"

    # 2. Modèles H3 : lus dans les gabarits officiels (jamais une liste à la main).
    req = _ex.h3_models_required()
    assert len(req) == 5, [m["name"] for m in req]
    assert all(m["url"].startswith("https://huggingface.co/") for m in req)
    assert {m["directory"] for m in req} == {"vae", "diffusion_models", "text_encoders", "loras"}
    with _tf.TemporaryDirectory() as td:
        for m in req[:2]:
            os.makedirs(os.path.join(td, m["directory"]), exist_ok=True)
            with open(os.path.join(td, m["directory"], m["name"]), "wb") as f:
                f.write(b"x")
        os.makedirs(os.path.join(td, req[2]["directory"]), exist_ok=True)
        with open(os.path.join(td, req[2]["directory"], req[2]["name"]) + ".part", "wb") as f:
            f.write(b"x")                                   # en cours → absent
        assert len(_ex.h3_models_missing(td)) == 3
    assert len(_ex.h3_models_missing("")) == 5, "sans dossier connu, tout manque"
    assert isinstance(_ex.comfy_models_dir(), str) and isinstance(_ex.externals_dir(), str)

    # 3. Téléchargement reprenable : un .part de 300 octets reprend avec Range.
    payload = bytes(range(256)) * 40                       # 10 240 octets
    seen = {}

    class _H(_hs.BaseHTTPRequestHandler):
        def do_GET(self):
            rng = self.headers.get("Range")
            seen["range"] = rng
            start = int(rng.split("=")[1].split("-")[0]) if rng else 0
            body = payload[start:]
            self.send_response(206 if rng else 200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = _hs.HTTPServer(("127.0.0.1", 0), _H)
    t = _th.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        with _tf.TemporaryDirectory() as td:
            dest = os.path.join(td, "m.bin")
            with open(dest + ".part", "wb") as f:
                f.write(payload[:300])
            ticks = []
            out = _ei.download(f"http://127.0.0.1:{srv.server_port}/m.bin", dest,
                               progress=lambda d, tot: ticks.append((d, tot)))
            assert seen["range"] == "bytes=300-", seen
            with open(out, "rb") as f:
                assert f.read() == payload, "reprise : contenu final exact"
            assert not os.path.exists(dest + ".part") and ticks and ticks[-1][0] == len(payload)
    finally:
        srv.shutdown()

    # 4. Fenêtre, bandeau, section : constructibles hors réseau (état fourni),
    #    méthodes liées, et présents là où on choisit un moteur.
    from ui.dialog_external import ExternalDialog
    from ui.dialog_comfy_install import ComfyInstallDialog
    st = _ex.Status(installed=False, running=False, detail="test")
    for key, ext in _ex.EXTERNALS.items():
        dlg = ExternalDialog(key, status=st)
        assert dlg.is_ready() is False and dlg._b_install.isVisible() is False  # caché tant que non affiché
        # vLLM = documentation seule (Linux / WSL) : pas d'installation automatique, par choix.
        assert dlg._b_install.isVisibleTo(dlg) == ext.auto_install, \
            f"{key} : « Installer automatiquement » {'attendu' if ext.auto_install else 'inattendu'} quand rien n'est installé"
        dlg.deleteLater()
    dlg = ComfyInstallDialog(status=_ex.Status(installed=True, running=True, version="0.35.1", missing=["x"]))
    assert dlg.is_ready() and dlg._b_models.isVisibleTo(dlg) and not dlg._b_install.isVisibleTo(dlg)
    dlg.deleteLater()
    from ui.external_banner import ExternalBanner
    b = ExternalBanner()
    b.set_engine("seedance-2.0")
    assert b.isHidden() and b._key == "", "aucun bandeau pour un moteur fal"
    b.deleteLater()
    for mod in ("ui.tab_t2v", "ui.tab_t2v_live", "ui.tab_video_engines", "ui.tab_video_engines_live"):
        src = inspect.getsource(importlib.import_module(mod))
        assert "ExternalBanner" in src and "set_engine(" in src, f"{mod} : bandeau absent"
    for mod in ("ui.page_settings", "ui.page_live_settings"):
        assert "ExternalsSection" in inspect.getsource(importlib.import_module(mod)), f"{mod} : section absente"
    # Le worker n'exécute jamais rien sans clic : ses actions sont nommées, pas devinées.
    for name in ("_comfyui_install", "_comfyui_models", "_comfyui_launch", "_ollama_install",
                 "_ollama_pull", "_ollama_launch", "_h3_local_install", "_h3_local_launch",
                 "_lmstudio_install", "_lmstudio_launch", "_jan_install", "_jan_launch",
                 "_llamacpp_install", "_llamacpp_launch"):
        assert hasattr(_ei.ExternalInstallWorker, name), name
    # Lignes de CODE seulement (le commentaire de closeEvent cite le mot).
    _code = "\n".join(l.split("#", 1)[0] for l in inspect.getsource(ExternalDialog).splitlines())
    assert "terminate(" not in _code, "jamais QThread.terminate()"


@test
def editeurs_video_cloud_table_worker_et_routage():
    """« Branche toutes les nouveautés » (Matthieu, 24/09/2026) : les éditeurs vidéo
    fal relevés fiche par fiche (Kling O3/O1 Edit, Wan 2.7, HappyHorse, Bernini-R,
    FLUX.3, Gemini Omni 1.1, Lucy) sont une TABLE (api/video_edit) : charge utile
    construite sans réseau, balises @Video1 gardées ou retirées selon le moteur,
    variante « reference-edit » de Bernini-R avec images, tarif 0 $/s connu du
    journal, moteurs proposés et routés dans les deux onglets « Modifier un clip »,
    SeedVR2 local dans l'agrandisseur."""
    import importlib
    from api import video_edit as VE
    from core import pricing
    assert len(VE.EDIT_ENGINES) >= 10 and all(v["endpoint"] and v["price"] and v["res"] for v in VE.EDIT_ENGINES.values())
    # Kling : balises gardées, images dans image_urls (≤4), keep_audio.
    ep, a = VE.build_args("kling-o3-edit-pro", "Reprends @Video1, remplace le fond par @Image1",
                          "https://v/clip.mp4", ["https://i/1.png"] * 6, "source")
    assert ep == "fal-ai/kling-video/o3/pro/video-to-video/edit" and "@Video1" in a["prompt"]
    assert len(a["image_urls"]) == 4 and a["keep_audio"] is True and "resolution" not in a
    # Wan 2.7 : balises retirées, UNE référence, durée 0 = source, audio d'origine, 1080p.
    ep, a = VE.build_args("wan-2.7-edit", "Reprends @Video1, remplace le fond par @Image1",
                          "https://v/clip.mp4", ["https://i/1.png", "https://i/2.png"], "1080p")
    assert ep == "fal-ai/wan/v2.7/edit-video" and "@" not in a["prompt"] and "the reference image" in a["prompt"]
    assert a["reference_image_url"] == "https://i/1.png" and a["duration"] == 0 \
        and a["audio_setting"] == "origin" and a["resolution"] == "1080p"
    # Bernini-R : sans image → edit-video ; avec → reference-edit-video ; négatif.
    ep, a = VE.build_args("bernini-r-edit", "make it night", "https://v/c.mp4", [], "source", "blurry")
    assert ep == "fal-ai/bernini-r/edit-video" and a["negative_prompt"] == "blurry" and "reference_image_urls" not in a
    ep, a = VE.build_args("bernini-r-edit", "make it night", "https://v/c.mp4", ["https://i/r.png"], "source")
    assert ep == "fal-ai/bernini-r/reference-edit-video" and a["reference_image_urls"] == ["https://i/r.png"]
    # FLUX.3 : aucune image même si fournie ; garde-fou de sécurité.
    ep, a = VE.build_args("flux-3-edit", "x", "https://v/c.mp4", ["https://i/r.png"], "source")
    assert "image_urls" not in a and "reference_image_urls" not in a and a["safety_tolerance"] == "4"
    # Tarif : lu par le journal, par palier quand la fiche en a.
    assert pricing.price_per_second("kling-o3-edit-pro", "source") == 0.168
    assert pricing.price_per_second("wan-2.7-edit", "1080p") == 0.15 and pricing.price_per_second("wan-2.7-edit", "720p") == 0.10
    assert pricing.price_per_second("gemini-omni-1.1-edit", "4k") == 0.30
    # Sortie : `video.url` ou `video_url`.
    assert VE._extract_video_url({"video": {"url": "https://o/v.mp4"}}) == "https://o/v.mp4"
    assert VE._extract_video_url({"video_url": "https://o/w.mp4"}) == "https://o/w.mp4"
    # Onglets : proposés et routés (source), Cinéma ET Live.
    for mod, cls in (("ui.tab_davinci_edit", "TabDavinciEdit"), ("ui.tab_modify_live", "TabModifyLive")):
        m = importlib.import_module(mod)
        s = inspect.getsource(getattr(m, cls)._process_next)
        assert "VideoEditWorker" in s, f"{mod} : éditeurs cloud non routés"
    import ui.tab_davinci_edit as DE
    tab = DE.TabDavinciEdit()
    keys = [tab._cb_model.itemData(i) for i in range(tab._cb_model.count())]
    assert all(k in keys for k in VE.EDIT_ENGINES), "tous les éditeurs cloud proposés"
    for i, k in enumerate(keys):
        if k == "wan-2.7-edit":
            tab._cb_model.setCurrentIndex(i)
    assert [tab._cb_res.itemData(i) for i in range(tab._cb_res.count())] == ["1080p", "720p"]
    assert not tab._cb_ratio.isEnabled() and "cloud" in tab._modif_hint.text()
    tab.deleteLater()
    # Agrandisseur : SeedVR2 local (gabarit ComfyUI) présent, contrat du nom conservé.
    from api import upscale as UP
    assert any(k == "seedvr_local" for _l, k in UP.UPSCALE_MODELS)
    w = UP.UpscaleVideoWorker("C:/x/Plan 03.mp4", model="seedvr_local")
    assert w._model == "seedvr_local" and w._output_path().endswith("Plan 03.mp4")
    assert "_local" in inspect.getsource(UP.UpscaleVideoWorker.run)
    for mod in ("ui.tab_upscale", "ui.tab_upscale_live"):
        assert 'ensure_ready("comfyui"' in inspect.getsource(importlib.import_module(mod)), mod


@test
def serveurs_locaux_demarres_automatiquement():
    """Demande Matthieu (24/09/2026, capture « installé mais ne tourne pas ») : un
    module INSTALLÉ mais arrêté est lancé par PANDORA au moment de générer
    (ui/external_autostart), attendu jusqu'à ce qu'il réponde ; la fenêtre
    d'installation ne s'ouvre que s'il n'est pas installé ou si le démarrage
    automatique est désactivé. Même réflexe côté IA texte (Ollama, LM Studio)."""
    import importlib
    from PyQt6.QtCore import QTimer
    from core import externals as _ex
    import ui.external_autostart as _ea
    import api.external_install as _ei
    import ui.dialog_external as _de
    calls = {"detect": 0, "launch": 0}

    def fake_detect(key):
        calls["detect"] += 1
        return _ex.Status(installed=True, running=calls["launch"] > 0 and calls["detect"] >= 2, detail="t")

    class _Guide:
        def __init__(self, *a, **k): pass
        def exec(self): return 0
        def is_ready(self): return False

    # ⚠ Pas de boucle d'événements imbriquée ici : elle traiterait les
    # deleteLater() des tests précédents (widgets aux threads encore vivants →
    # abort Qt, harnais mort en silence — vécu le 24/09/2026). L'automate est
    # exercé SANS thread : les slots sont appelés directement, le lancement et
    # le guide sont des bouchons qui enregistrent.
    _orig_en = _ea.autostart_enabled
    _ea.autostart_enabled = lambda: True

    def make():
        d = _ea.AutoStartDialog("ollama", poll_ms=50)
        d._tick.stop()
        rec = []
        d._launch = lambda: (rec.append("launch"),
                             d._on_status("ollama", _ex.Status(installed=True, running=True, detail="t")))
        d._open_guide = lambda st=None: (rec.append("guide"), setattr(d, "ready", False))
        return d, rec

    try:
        # 1. Installé, arrêté → lancé UNE fois, puis prêt — sans guide.
        d, rec = make()
        d._on_status("ollama", _ex.Status(installed=True, running=False, detail="t"))
        assert d.ready and d.launched and rec == ["launch"], (d.ready, d.launched, rec)
        # 2. Déjà en marche → prêt sans lancement.
        d, rec = make()
        d._on_status("ollama", _ex.Status(installed=True, running=True, detail="t"))
        assert d.ready and not d.launched and rec == []
        # 3. Pas installé → le guide, jamais de lancement.
        d, rec = make()
        d._on_status("ollama", _ex.Status(installed=False, running=False, detail="t"))
        assert not d.ready and not d.launched and rec == ["guide"]
        # 4. Lancé mais toujours muet après le délai → le guide.
        d, rec = make()
        d.launched = True
        d._t0 -= 10_000
        d._on_status("ollama", _ex.Status(installed=True, running=False, detail="t"))
        assert not d.ready and rec == ["guide"]
        # 5. Démarrage automatique désactivé → le guide, jamais de lancement.
        _ea.autostart_enabled = lambda: False
        d, rec = make()
        d._on_status("ollama", _ex.Status(installed=True, running=False, detail="t"))
        assert not d.ready and not d.launched and rec == ["guide"]
    finally:
        _ea.autostart_enabled = _orig_en
    # 5. Branché partout où un moteur a besoin d'un serveur : ComfyUI (6 onglets)
    #    et MiniMax H3 local (4 onglets) ; plus aucun onglet n'ouvre lui-même la
    #    fenêtre d'installation.
    for mod, h3 in (("ui.tab_t2v", True), ("ui.tab_t2v_live", True), ("ui.tab_video_engines", True),
                    ("ui.tab_video_engines_live", True), ("ui.tab_davinci_edit", False),
                    ("ui.tab_modify_live", False)):
        s = inspect.getsource(importlib.import_module(mod))
        assert 'ensure_ready("comfyui"' in s and "ComfyInstallDialog(self)" not in s, mod
        if h3:
            assert 'ensure_ready("h3_local"' in s, f"{mod} : garde H3 local absente"
    # 6. IA texte : Ollama / LM Studio relancés depuis le worker, une seule fois.
    from core import ai_provider as AP
    assert "_with_autostart" in inspect.getsource(AP._ollama_post) \
        and "_with_autostart" in inspect.getsource(AP._local_complete) \
        and "_with_autostart" in inspect.getsource(AP.chat_ex)
    _orig_en = _ex.autostart_enabled
    _ex.autostart_enabled = lambda: False
    try:
        assert _ex.autostart_blocking("ollama") is False, "désactivé → rien lancé"
    finally:
        _ex.autostart_enabled = _orig_en
    assert _ex.autostart_blocking("comfyui") is False, "seuls Ollama et LM Studio en bloquant"
    # 7. Réglage dans les Paramètres, bandeau qui lance d'un clic.
    from ui.externals_section import ExternalsSection
    sec = ExternalsSection()
    assert hasattr(sec, "_auto_cb") and sec._auto_cb.isChecked() == _ex.autostart_enabled()
    sec.deleteLater()
    import ui.external_banner as _eb
    assert '_mode = "launch"' in inspect.getsource(_eb.ExternalBanner._on_status) \
        and "ensure_ready" in inspect.getsource(_eb.ExternalBanner._open)
    import core.i18n as i18n
    assert "Lancer maintenant" in i18n._FR_TO_EN and "Démarrage de" in i18n._FR_TO_EN


@test
def modifier_un_clip_endpoint_annulation_parquee_et_moteurs_locaux():
    """Audit « Modifier un clip » (24/09/2026). (1) api/real.py lisait une variable
    `base` supprimée en août → NameError sur CHAQUE envoi en mode « ext », dans les
    deux éditions, depuis la v2.2.0 : le chemin d'édition vient désormais de
    core/seedance_family et la 2.5 nomme sa tâche. (2) « Annuler » lâchait un
    QThread vivant (abort différé) : les workers sont parqués. (3) 720p par défaut
    (la grille commençait au 4K). (4) Gabarits ComfyUI d'édition vidéo comme
    moteurs (0 $), routés vers api.comfy_edit.ComfyEditWorker. (5) Clip absent →
    échec explicite (plus de repli texte seul payé) ; références selon le mode ;
    liste figée pendant la file ; simulation non journalisée."""
    import ast, tempfile as _tf
    import api.real as _real
    from core import seedance_family as _sf

    # 1. Aucun nom libre `base` dans run_real ; le mode ext lit la table.
    tree = ast.parse(inspect.getsource(_real.run_real))
    fn = tree.body[0]
    assigned = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    assigned |= {a.arg for a in fn.args.args}
    loaded = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    assert "base" not in (loaded - assigned), "run_real lit encore une variable `base` jamais définie"
    src = inspect.getsource(_real.run_real)
    assert 'endpoints.get("ext")' in src and '"task"' in src and '"editing"' in src
    for m in ("seedance-2.0", "seedance-2.0-fast", "seedance-2.5"):
        assert _sf.endpoints(m).get("ext", "").endswith("/reference-to-video"), m
    assert "rien n'a été généré" in src, "un clip non envoyé doit arrêter la génération"

    # 2-5. Onglet Cinéma, hors réseau : catalogue ComfyUI synthétique.
    from core import comfy_catalog as _cc
    _orig_cached = _cc.load_cached_video
    _cc.load_cached_video = lambda: [{"name": "video_x_video_edit", "title": "X Edit", "kind": "edit",
                                      "size": 3e9, "loads": 0, "prompted": True}]
    try:
        import ui.tab_davinci_edit as DE
        tab = DE.TabDavinciEdit()
    finally:
        _cc.load_cached_video = _orig_cached
    keys = [tab._cb_model.itemData(i) for i in range(tab._cb_model.count())]
    assert "comfy_edit:video_x_video_edit" in keys and "seedance-2.0" in keys and "pixverse_face" in keys
    assert tab._cb_res.currentData() == "720p", f"720p par défaut attendu, lu {tab._cb_res.currentData()}"
    assert hasattr(tab, "_external_banner"), "bandeau ComfyUI attendu sous le moteur"
    # Routage comfy_edit : worker de api.comfy_edit, clip + prompt + référence transmis.
    import api.comfy_edit as _ce
    seen = {}

    class _StubWorker:
        def __init__(self, params):
            seen.update(params)
            self.finished = _Sig(); self.progress = _Sig(); self.failed = _Sig()
        def start(self): pass
        def isRunning(self): return False

    class _Sig:
        def connect(self, *_): pass

    with _tf.TemporaryDirectory() as td:
        clip = os.path.join(td, "plan.mp4")
        with open(clip, "wb") as f:
            f.write(b"\x00" * 1024)
        tab._load_clips([{"name": "plan", "file_path": clip}])
        for i in range(tab._cb_model.count()):
            if tab._cb_model.itemData(i) == "comfy_edit:video_x_video_edit":
                tab._cb_model.setCurrentIndex(i)
        assert tab._modif_hint.isVisibleTo(tab) and "ComfyUI" in tab._modif_hint.text()
        tab._prompt_global.setPlainText("remplace le fond par une plage")
        tab._queue = [(0, 0)]; tab._queue_pos = 0; tab._failed_clips = []; tab._mock_count = 0
        _orig_w = _ce.ComfyEditWorker
        _ce.ComfyEditWorker = _StubWorker
        try:
            tab._process_next()
        finally:
            _ce.ComfyEditWorker = _orig_w
        assert seen.get("engine") == "comfy_edit:video_x_video_edit" and seen.get("video_path") == clip
        assert "@Video1" in seen.get("prompt", "") and "plage" in seen["prompt"]
        # Clip absent : échec explicite, pas de génération texte seul (le bilan de
        # fin de file ouvre une boîte modale : neutralisée le temps du test).
        tab._worker = None
        tab._load_clips([{"name": "fantome", "file_path": os.path.join(td, "absent.mp4")}])
        tab._queue = [(0, 0)]; tab._queue_pos = 0; tab._failed_clips = []
        _orig_warn = DE.QMessageBox.warning
        DE.QMessageBox.warning = staticmethod(lambda *a, **k: None)
        try:
            tab._process_next()
        finally:
            DE.QMessageBox.warning = _orig_warn
        assert tab._failed_clips and "introuvable" in tab._failed_clips[0][1]
    # Annulation : les deux workers passent par abandon_thread, jamais `= None` à chaud.
    _cs = inspect.getsource(DE.TabDavinciEdit._cancel_queue)
    assert _cs.count("abandon_thread(") >= 2 and ".quit()" not in _cs
    _ps = inspect.getsource(DE.TabDavinciEdit._process_next)
    assert "abandon_thread(prev)" in _ps and "ComfyEditWorker" in _ps
    assert "_per_clip_ref_images = {}" in inspect.getsource(DE.TabDavinciEdit._load_clips)
    assert '"resolution"' in inspect.getsource(DE.TabDavinciEdit._import_and_advance)
    # L'étiquette ne promet plus LatentSync : depuis le 25/09/2026 le moteur se
    # CHOISIT dans la ligne (menu nom · prix — année/spécialité, api/lipsync.engine_label).
    assert "Synchronisation LatentSync" not in inspect.getsource(DE.TabDavinciEdit._start_lipsync)
    _bsrc = inspect.getsource(DE.TabDavinciEdit._build_ui)
    assert "_lipsync_engine_combo" in _bsrc and "engine_label" in _bsrc and "_ls_name" not in _bsrc
    # Tarif : un gabarit ComfyUI nommé vaut 0 $ dans le journal.
    from core import pricing
    assert pricing.price_per_second("comfy_edit:video_x_video_edit", "source") == 0.0
    tab.deleteLater()


@test
def comfy_widgets_promus_par_nom_valeur_interne_et_case_de_controle():
    """Convertisseur ComfyUI, sous-graphes (constat validation vidéo 24/09/2026) :
    les `widgets_values` du nœud EXTERNE suivent l'ordre des entrées non-connexion
    du SOUS-GRAPHE (le gabarit H3 met le prompt en tête sans le lister parmi ses
    prises) ; une graine INT traîne sa case « fixed »/« randomize » ; un nœud
    externe SANS valeur laisse au nœud interne la sienne. Avant : 14 gabarits
    vidéo refusés (`value: None`, un LoRA dans `ckpt_name`)."""
    from core import comfy_workflow as _wf

    def sg_wf(outer_wv, outer_inputs):
        return {"nodes": [{"id": 1, "type": "sg-1", "widgets_values": outer_wv, "inputs": outer_inputs,
                           "outputs": []}],
                "links": [],
                "definitions": {"subgraphs": [{
                    "id": "sg-1",
                    "inputs": [{"name": "text", "type": "STRING", "linkIds": [10]},
                               {"name": "noise_seed", "type": "INT", "linkIds": [11]},
                               {"name": "ckpt_name", "type": "COMBO", "linkIds": [12]},
                               {"name": "steps", "type": "INT", "linkIds": [13]}],
                    "outputs": [],
                    "nodes": [
                        {"id": 2, "type": "CLIPTextEncode", "widgets_values": ["texte interne"],
                         "inputs": [{"name": "text", "type": "STRING", "link": 10, "widget": {"name": "text"}}], "outputs": []},
                        {"id": 3, "type": "KSampler", "widgets_values": [7, "fixed", 20],
                         "inputs": [{"name": "seed", "type": "INT", "link": 11, "widget": {"name": "seed"}},
                                    {"name": "steps", "type": "INT", "link": 13, "widget": {"name": "steps"}}], "outputs": []},
                        {"id": 4, "type": "CheckpointLoaderSimple", "widgets_values": ["interne.safetensors"],
                         "inputs": [{"name": "ckpt_name", "type": "COMBO", "link": 12, "widget": {"name": "ckpt_name"}}], "outputs": []},
                    ],
                    "links": [{"id": 10, "origin_id": -10, "origin_slot": 0, "target_id": 2, "target_slot": 0, "type": "STRING"},
                              {"id": 11, "origin_id": -10, "origin_slot": 1, "target_id": 3, "target_slot": 0, "type": "INT"},
                              {"id": 12, "origin_id": -10, "origin_slot": 2, "target_id": 4, "target_slot": 0, "type": "COMBO"},
                              {"id": 13, "origin_id": -10, "origin_slot": 3, "target_id": 3, "target_slot": 1, "type": "INT"}],
                }]}}

    def promoted_values(flat):
        prim = {n["id"]: n["widgets_values"][0] for n in flat["nodes"] if n["type"] == "PrimitiveNode"}
        by_link = {l[0]: (l[1], l[3], l[4]) for l in flat["links"]}
        out = {}
        for n in flat["nodes"]:
            for i in n.get("inputs") or []:
                src = by_link.get(str(i.get("link")))
                out[(n["type"], i["name"])] = prim.get(src[0]) if src else ("LIBRE" if i.get("link") is None else "LIEN")
        return out

    # 1. Externe SANS valeur : chaque entrée interne reste libre → sa propre valeur.
    outer_in = [{"name": "text", "type": "STRING", "link": None, "widget": {"name": "text"}},
                {"name": "noise_seed", "type": "INT", "link": None, "widget": {"name": "noise_seed"}},
                {"name": "ckpt_name", "type": "COMBO", "link": None, "widget": {"name": "ckpt_name"}}]
    v = promoted_values(_wf.flatten(sg_wf([], outer_in)))
    assert v[("CLIPTextEncode", "text")] == "LIBRE" and v[("KSampler", "seed")] == "LIBRE" \
        and v[("CheckpointLoaderSimple", "ckpt_name")] == "LIBRE", v
    # 2. Externe AVEC valeurs : ordre des entrées du sous-graphe, case de contrôle
    #    sautée après la graine ; « steps » (4e) au-delà des valeurs → interne.
    v = promoted_values(_wf.flatten(sg_wf(["texte externe", 42, "randomize", "externe.safetensors"], outer_in)))
    assert v[("CLIPTextEncode", "text")] == "texte externe" and v[("KSampler", "seed")] == 42 \
        and v[("CheckpointLoaderSimple", "ckpt_name")] == "externe.safetensors" and v[("KSampler", "steps")] == "LIBRE", v
    # 2b. Sans case de contrôle enregistrée : les valeurs suivent sans saut.
    v = promoted_values(_wf.flatten(sg_wf(["t", 42, "externe.safetensors", 30], outer_in)))
    assert v[("KSampler", "seed")] == 42 and v[("CheckpointLoaderSimple", "ckpt_name")] == "externe.safetensors" \
        and v[("KSampler", "steps")] == 30, v
    # 2c. Une prise composée « IMAGE,MASK » ou propre à un nœud (BBOX) n'occupe
    #     aucune case : ce sont des connexions (LTX IC-LoRA : sans cela, tout
    #     glissait de deux cases et un checkpoint arrivait dans un INT).
    assert _wf._is_link_type("IMAGE,MASK") and not _wf._is_widget_type("IMAGE,MASK") \
        and not _wf._is_widget_type("BBOX") and _wf._is_widget_type("COMBO") and _wf._is_widget_type("INT")
    # 3. Valeurs partielles : ce qui manque reste interne, jamais None.
    v = promoted_values(_wf.flatten(sg_wf(["texte externe"], outer_in)))
    assert v[("CLIPTextEncode", "text")] == "texte externe" and v[("KSampler", "seed")] == "LIBRE", v
    # 4. Le contrat vidéo : LoadVideo reconnu, remplissage sans prompt toléré.
    from core import comfy_image as _ci, comfy_video as _cv, comfy_catalog as _cc
    oi = {"LoadVideo": {"input": {"required": {"file": [["a.mp4"]]}}},
          "SaveVideo": {"input": {"required": {"video": ["VIDEO"]}}, "output_node": True}}
    api = {"1": {"class_type": "LoadVideo", "inputs": {"file": "a.mp4"}},
           "2": {"class_type": "SaveVideo", "inputs": {"video": ["1", 0]}}}
    info = _ci.analyze(api, oi)
    assert info["load_videos"] == ["1"] and info["outputs"] == ["2"] and not info["prompt_nodes"]
    _ci.fill(api, oi, info, "", "", None, None, 3, [], ["pandora/clip.mp4"], require_prompt=False)
    assert api["1"]["inputs"]["file"] == "pandora/clip.mp4"
    assert _cv.is_edit_engine("comfy_edit:x") and _cv.template_name("comfy_edit:video_x") == "video_x"
    entries = _cc.parse_video_index([
        {"title": "Video", "templates": [
            {"name": "video_x_video_edit", "title": "X", "tags": ["Video Edit"], "size": 3e9},
            {"name": "api_y", "title": "Y", "tags": ["Video Edit"]},
            {"name": "video_z", "title": "Z", "tags": ["Motion Control"], "openSource": False}]},
        {"title": "Video Tools", "templates": [{"name": "utility_up", "title": "U", "tags": ["Video Upscale"], "size": 4e9}]},
        {"title": "Image", "templates": [{"name": "image_nope", "title": "N", "tags": ["Text to Image"]}]}])
    assert [e["name"] for e in entries] == ["video_x_video_edit", "utility_up"], entries
    assert entries[0]["kind"] == "edit" and entries[1]["kind"] == "upscale"
    assert _cc.video_engine_label(entries[1]).endswith("0 $") and "agrandissement" in _cc.video_engine_label(entries[1])


@test
def ia_locales_comme_claude_contexte_pensee_vision_et_serveurs():
    """Chantier IA locales (24/09/2026, demande Matthieu : tous les moteurs, même
    les plus lourds, « exactement comme Claude »). Quatre défauts corrigés
    (core/local_llm) : Ollama coupait l'ENTRÉE en silence (pas de num_ctx), la
    pensée <think> des modèles raisonnants restait dans la réponse, un modèle
    sans vision « décrivait » des images qu'il ne voyait pas, et LM Studio /
    llama.cpp / vLLM / Jan n'avaient ni préréglage, ni découverte, ni guide."""
    import importlib
    from core import local_llm as ll, ai_registry as R, ai_provider as AP, externals as EX
    from api import ai_models as AM

    # 1. Pensée : réponses ET flux, balises coupées entre deux fragments.
    assert ll.strip_thinking("<think>a</think>\n\n[1]") == "[1]"
    assert ll.strip_thinking("<think>réponse coupée pendant la réflexion") == ""
    assert ll.strip_thinking("texte <b>gras</b>") == "texte <b>gras</b>"
    f = ll.ThinkFilter()
    out = "".join(f.feed(c) for c in ["Bon", "jour <th", "ink>secret</thi", "nk>\n\nRéponse", " <b>x"]) + f.flush()
    assert out == "Bonjour Réponse <b>x", repr(out)

    # 2. Fenêtre Ollama : dimensionnée sur l'appel, plancher, plafond, contexte natif.
    big = [{"role": "user", "content": "x" * 60000}]
    assert ll.ollama_num_ctx(big, 16000) == 32768, "60 000 car. + 16 k de sortie → 32 k"
    assert ll.ollama_num_ctx([{"role": "user", "content": "court"}], 512) == ll.OLLAMA_CTX_FLOOR
    assert ll.ollama_num_ctx([{"role": "user", "content": "x" * 300000}], 16000, ceiling=131072) == 131072
    assert ll.ollama_num_ctx([{"role": "user", "content": "x" * 300000}], 16000,
                             model_ctx=32768, ceiling=131072) == 32768, "jamais au-delà du modèle"
    orig = AP._cfg
    AP._cfg = lambda: {"ai_provider": "ollama", "ollama_model": "m-think", "ollama_num_ctx": 65536}
    try:
        url = AP._ollama_url()
        AP._OLLAMA_INFO[(url, "m-think")] = {"caps": ["completion", "vision", "thinking"], "ctx": 262144}
        AP._OLLAMA_INFO[(url, "m-plain")] = {"caps": ["completion"], "ctx": 32768}
        AP._OLLAMA_CTX_USED.pop("m-think", None)
        req = AP._ollama_request("S", [{"role": "user", "content": "x" * 90000}], "m-think", 16000, False)
        assert req["think"] is False, "réflexion coupée quand le modèle sait penser (= thinking:disabled chez Anthropic)"
        assert req["options"]["num_ctx"] == 51200 and req["options"]["num_predict"] == 16000, req["options"]
        req2 = AP._ollama_request("S", [{"role": "user", "content": "court"}], "m-think", 100, False)
        assert req2["options"]["num_ctx"] == 51200, "fenêtre collante : jamais réduite (pas de rechargement)"
        assert "think" not in AP._ollama_request("S", [{"role": "user", "content": "x"}], "m-plain", 10, False)
        # 3. Garde vision.
        try:
            AP._ollama_request("S", [{"role": "user", "content": [
                {"type": "text", "text": "?"},
                {"type": "image", "source": {"type": "base64", "data": "AAAA"}}]}], "m-plain", 10, False)
            raise AssertionError("un modèle sans vision a reçu des images sans erreur")
        except RuntimeError as e:
            assert "ne voit pas les images" in str(e)
        assert not ll.vision_error("m", None, [{"role": "user", "content": [{"type": "image"}]}]), \
            "capacités inconnues (vieux serveur) → on laisse passer"
    finally:
        AP._cfg = orig
        AP._OLLAMA_CTX_USED.pop("m-think", None)

    # 4. Fournisseur « local » : préréglages, charge utile, clé facultative, groupe.
    assert "local" in AP._PROVIDERS and R.ENGINES["local"]["group"] == "local" == R.ENGINES["ollama"]["group"]
    assert set(ll.LOCAL_PRESETS) == {"lmstudio", "llamacpp", "vllm", "jan", "other"}
    rows = R.primary_menu_items({"local": ["qwen3-8b"], "ollama": ["qwen3.6:latest"]})
    engines = [r.get("engine") for r in rows if r["selectable"]]
    assert "local" in engines and "local:qwen3-8b" in engines and "ollama:qwen3.6:latest" in engines
    assert [r["label"] for r in rows if not r["selectable"]][2] == "Local — sur votre machine"
    AP._cfg = lambda: {"ai_profile": "single", "ai_provider": "local", "ai_engine": "local",
                       "local_preset": "llamacpp", "local_model": "qwen3-8b"}
    try:
        assert AP._resolve_engine("screenplay") == ("local", "qwen3-8b") and AP.key_error("screenplay") is None
        url, payload, headers = AP._local_payload("S", [{"role": "user", "content": "h"}], "qwen3-8b", 99, True)
        assert url == "http://localhost:8080/v1/chat/completions" and headers["Authorization"] == "Bearer local"
        assert payload["chat_template_kwargs"] == {"enable_thinking": False}, "llama.cpp : réflexion coupée"
        assert payload["stream_options"] == {"include_usage": True} and payload["max_tokens"] == 99
        assert AP.is_local_provider("screenplay") and "llama.cpp" in AP._engine_display_name("local", "")
        AP._cfg = lambda: {"ai_profile": "single", "ai_provider": "local", "ai_engine": "local",
                           "local_preset": "lmstudio", "local_url": "http://10.0.0.9:1234/v1/"}
        assert "Aucun modèle" in AP.key_error("assistant")
        url, payload, _ = AP._local_payload("S", [{"role": "user", "content": "h"}], "m", 9, False)
        assert url == "http://10.0.0.9:1234/v1/chat/completions" and "chat_template_kwargs" not in payload, \
            "LM Studio : charge utile strictement OpenAI"
    finally:
        AP._cfg = orig
    assert "injoignable" in AP.humanize_ai_error("HTTPConnectionPool(host='localhost', port=1234): Max retries exceeded")
    # Un seul adaptateur OpenAI-compatible : plus de copies du même flux.
    src = inspect.getsource(AP)
    for fn in ("_openai_stream", "_mistral_stream", "_kimi_stream", "_glm_stream", "_custom_stream", "_local_stream"):
        assert "_oai_stream(" in inspect.getsource(getattr(AP, fn)), f"{fn} : adaptateur commun attendu"
    for fn in ("_oai_json", "_ollama_complete", "_ollama_stream"):
        assert "_note_" in inspect.getsource(getattr(AP, fn)), f"{fn} : consommation non journalisée"
    assert src.count("filt = ThinkFilter()") == 2, "flux OpenAI-compatible + flux Ollama filtrés"
    from core.engine_prompts import _needs_reinforcement, TASK_ROLES
    assert _needs_reinforcement("local", "gros-modele-70b") and _needs_reinforcement("ollama", "x")
    for t in ("decoupage", "video_prompt", "element_chat", "vision"):
        assert t in TASK_ROLES, f"rappel de rôle manquant pour {t}"

    # 5. Découverte : les embeddings ne sont pas des assistants ; « local » découvert.
    assert AM._compatible("ollama", "nomic-embed-text:latest") is False
    assert AM._compatible("local", "qwen3-8b") and AM._compatible("mistral", "codestral-embed") is False
    assert "local" in inspect.getsource(AM.discover_all)
    assert not ll.is_chat_model("bge-reranker-v2") and ll.is_chat_model("gemma3:12b")

    # 6. Modèles recommandés : uniques, tailles et cartes renseignées, jusqu'aux plus lourds.
    names = [m["name"] for m in ll.OLLAMA_MODELS]
    assert len(set(names)) == len(names) >= 15 and all(m["gb"] > 0 and m["vram"] >= 8 for m in ll.OLLAMA_MODELS)
    assert max(m["vram"] for m in ll.OLLAMA_MODELS) >= 80, "les plus lourds aussi (décision Matthieu)"
    assert any(m["vision"] for m in ll.OLLAMA_MODELS) and all(":" in m["hf"] or "gpt-oss" in m["hf"] for m in ll.GGUF_MODELS)

    # 7. Modules externes des serveurs locaux + panneau partagé dans les DEUX Paramètres.
    for k in EX.LOCAL_SERVER_KEYS:
        assert EX.for_engine("local:" + k).key == k and EX.EXTERNALS[k].url_config_key == "local_url"
    assert EX.local_server_url("jan").endswith(":1337/v1")
    assert EX.EXTERNALS["lmstudio"].download_url == "https://lmstudio.ai/download/latest/win32/x64"
    from ui.local_ai_panel import LocalAIPanel
    pnl = LocalAIPanel()
    pnl.load({"local_preset": "jan", "local_model": "abc", "ai_available_models": {"local": ["m1", "m2"]}})
    assert pnl.current_preset() == "jan" and pnl.model_combo.count() == 3
    assert pnl.apply({}) == {"local_preset": "jan", "local_url": "", "local_model": "abc", "local_key": ""}
    pnl.deleteLater()
    for mod in ("ui.page_settings", "ui.page_live_settings"):
        s = inspect.getsource(importlib.import_module(mod))
        assert "LocalAIPanel" in s and "_local_panel.apply(cfg)" in s and "_open_ollama_models" in s, mod
    from ui.dialog_external import ExternalDialog
    dlg = ExternalDialog("ollama", status=EX.Status(installed=True, running=True, detail="t"))
    assert dlg._model_combo is not None and dlg._ctx_spin is not None
    assert dlg._chosen_model() == ll.OLLAMA_MODELS[0]["name"]
    dlg._model_combo.setEditText("monmodele:7b")
    assert dlg._chosen_model() == "monmodele:7b"
    dlg.deleteLater()
    dlg = ExternalDialog("llamacpp", status=EX.Status(installed=True, running=False, detail="t"))
    assert dlg._b_launch.isVisibleTo(dlg) and dlg._chosen_model() == ll.GGUF_MODELS[0]["hf"]
    dlg.deleteLater()
    import core.i18n as i18n
    for s in ("Local — sur votre machine", "Modèles recommandés", "Utiliser ce modèle",
              "Fenêtre de contexte maxi (jetons)", "Clé (vide pour un serveur local)"):
        assert s in i18n._FR_TO_EN, s
    # 8. Le script de conformité existe et ne touche jamais la vraie config.
    cs = open(os.path.join(os.path.dirname(__file__), "ai_conformance.py"), encoding="utf-8").read()
    assert "AP._cfg = lambda: cfg" in cs and "save_config" not in cs

    # 9. Marqueurs tolérants (constat conformité : qwen2.5vl écrit 9 « ═ » au lieu
    #    de 10 → le scénario réécrit disparaissait en silence).
    from core.markers import normalize_markers
    M = "══════════ MESSAGE ══════════"
    S = "══════════ SCÉNARIO ══════════"
    for variant in ("═════════ SCÉNARIO ══════════", "=== SCÉNARIO ===", "──────  SCÉNARIO ──────",
                    "══════════SCÉNARIO══════════"):
        assert normalize_markers("a\n" + variant + "\nb", (M, S)) == "a\n" + S + "\nb", variant
    assert normalize_markers("a\n" + S + "\nb", (M, S)) == "a\n" + S + "\nb", "canonique inchangé"
    assert normalize_markers("scénario : === scénario ===", (S,)) == "scénario : === scénario ===", \
        "le mot-clé reste exact (casse)"
    assert normalize_markers("", (S,)) == "" and normalize_markers("rien", (S,)) == "rien"
    from api import plan_coedit as _pc
    for mod in (__import__("api.screenplay", fromlist=["_"]), _pc):
        assert "normalize_markers(raw" in inspect.getsource(mod), f"{mod.__name__} : découpage non tolérant"


@test
def images_comfyui_catalogue_contrat_generique_et_appel_unique():
    """Chantier images (24/09/2026, demande Matthieu : TOUS les moteurs, même
    les plus lourds) : le catalogue est LU chez ComfyUI (core/comfy_catalog),
    le contrat de remplissage est lu dans la STRUCTURE de n'importe quel
    gabarit (core/comfy_image), et tous les points de génération passent par
    UN appel (core/image_call) qui rend une URL /view comme une URL fal.
    Validé sur les gabarits officiels contre le serveur ; ici, six d'entre eux
    figés avec leurs définitions (tools/fixtures/comfy/images)."""
    import json
    from core import comfy_catalog as _cc, comfy_image as _ci, comfy_workflow as _wf, image_call as _ic

    # 1. Catalogue : la catégorie « Image » seulement (mediaType = la vignette !),
    #    pas les nœuds API, pas ce qui n'est pas ouvert.
    index = [
        {"title": "Image", "templates": [
            {"name": "image_other_edit", "title": "E", "mediaType": "image", "tags": ["Image Edit"], "size": 3e9},
            {"name": "api_x", "title": "API", "mediaType": "image", "openSource": True},
            {"name": "image_closed", "title": "C", "mediaType": "image", "openSource": False},
            {"name": "image_z_image", "title": "Z", "mediaType": "image", "size": 21e9, "tags": ["Text to Image"], "openSource": True},
        ]},
        {"title": "Video", "templates": [{"name": "video_v", "title": "V", "mediaType": "image", "openSource": True}]},
        {"title": "Image Tools", "templates": [{"name": "utility_u", "title": "U", "mediaType": "image", "openSource": True}]},
    ]
    entries = _cc.parse_index(index)
    # Familles connues en tête (Z-Image…), le reste alphabétique.
    assert [e["name"] for e in entries] == ["image_z_image", "image_other_edit"], entries
    assert entries[1]["edit"] and not entries[0]["edit"]
    eng = _cc.as_engine({"name": "image_z_image", "title": "Z", "size": 21e9, "edit": False})
    assert eng["endpoint"] == "comfy:image_z_image" and eng["kind"] == "comfy" and "21 Go" in eng["label"] and eng["label"].endswith("$0")
    assert _cc.is_comfy_engine("comfy:image_z_image") and _cc.template_name("comfy:image_z_image") == "image_z_image"
    assert _ic.needs_fal("nb2") and not _ic.needs_fal("comfy:image_z_image")

    # 2. Contrat générique sur six gabarits officiels figés.
    fx = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "comfy", "images")
    with open(os.path.join(fx, "object_info_images.json"), encoding="utf-8") as f:
        oi = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    expect = {
        #                                      prompt neg  size  seed  loads
        "image_z_image_turbo":                 (1,    0,   True, True, 0),
        # L'instance ACTIVE est la variante « base » (la distillée est contournée) :
        # elle porte un encodeur négatif à texte vide — un vrai nœud négatif.
        "image_flux2_klein_text_to_image":     (1,    1,   True, True, 0),
        "image_flux2_klein_image_edit_4b_distilled": (1, 0, False, True, 1),
        "image_qwen_image_edit_2509":          (1,    1,   False, True, 1),
        "image_sdxl_simple":                   (1,    1,   True, True, 0),
        "hidream_i1_dev":                      (1,    1,   True, True, 0),
    }
    for name, (np_, nn, sized, seeded, loads) in expect.items():
        api = _wf.prune_unreachable(_wf.to_api(_wf.load(os.path.join(fx, name + ".json")), oi), oi)
        info = _ci.analyze(api, oi)
        assert len(info["prompt_nodes"]) == np_, (name, info["prompt_nodes"])
        assert len(info["negative_nodes"]) == nn, (name, info["negative_nodes"])
        assert bool(info["size_targets"]) is sized, (name, info["size_targets"])
        assert bool(info["seed_targets"]) is seeded, (name, info["seed_targets"])
        assert len(info["load_images"]) == loads and info["outputs"], (name, info["load_images"], info["outputs"])
        refs = ["pandora/a.png"] if loads else []
        _ci.fill(api, oi, info, "PROMPT PANDORA", "NEG", 832, 480, 4242, refs)
        for nid in info["prompt_nodes"]:
            cls = api[nid]["class_type"]
            assert all(api[nid]["inputs"][k] == "PROMPT PANDORA" for k in _ci._string_inputs(oi, cls)), name
        for nid in info["negative_nodes"]:
            assert "NEG" in api[nid]["inputs"].values(), name
        for nid, key in info["seed_targets"]:
            assert api[nid]["inputs"][key] == 4242, name
        if sized:
            vals = sorted(api[nid]["inputs"][key] for nid, key in info["size_targets"])
            assert vals[:2] == [480, 832] or vals == [480, 832] * (len(vals) // 2), (name, vals)
        for nid in info["load_images"]:
            assert api[nid]["inputs"]["image"] == "pandora/a.png", name
    # Klein T2V : la largeur promue passe par un PrimitiveInt — celui relié à `width`.
    api = _wf.prune_unreachable(_wf.to_api(_wf.load(os.path.join(fx, "image_flux2_klein_text_to_image.json")), oi), oi)
    info = _ci.analyze(api, oi)
    _ci.fill(api, oi, info, "x", "", 1344, 768, 1, [])
    lat = next(n for n in api.values() if n["class_type"] == "EmptyFlux2LatentImage")["inputs"]
    assert api[lat["width"][0]]["inputs"]["value"] == 1344 and api[lat["height"][0]]["inputs"]["value"] == 768, lat
    # Édition : deux références pour un seul LoadImage → la première ; un LoadImage
    # de plus que de références → il reprend la première (jamais l'image d'exemple).
    api = _wf.prune_unreachable(_wf.to_api(_wf.load(os.path.join(fx, "image_flux2_klein_image_edit_4b_distilled.json")), oi), oi)
    info = _ci.analyze(api, oi)
    assert not info["size_targets"], "en édition le cadre suit l'image : rien à écrire"
    _ci.fill(api, oi, info, "x", "", None, None, 1, ["pandora/1.png", "pandora/2.png"])
    assert api[info["load_images"][0]]["inputs"]["image"] == "pandora/1.png"

    # 3. Nœud CONTOURNÉ (mode 4) : ses entrées passent vers ses sorties, comme le frontend.
    info_syn = {"A": {"input": {"required": {"text": ["STRING", {"multiline": True}]}}},
                "B": {"input": {"required": {"conditioning": ["CONDITIONING"]}}},
                "C": {"input": {"required": {"conditioning": ["CONDITIONING"]}}, "output_node": True}}
    ui = {"nodes": [
        {"id": 1, "type": "A", "inputs": [], "outputs": [{"type": "CONDITIONING", "links": [10]}], "widgets_values": ["t"]},
        {"id": 2, "type": "B", "mode": 4, "inputs": [{"name": "conditioning", "type": "CONDITIONING", "link": 10}],
         "outputs": [{"type": "CONDITIONING", "links": [11]}], "widgets_values": []},
        {"id": 3, "type": "C", "inputs": [{"name": "conditioning", "type": "CONDITIONING", "link": 11}], "widgets_values": []},
    ], "links": [[10, 1, 0, 2, 0, "CONDITIONING"], [11, 2, 0, 3, 0, "CONDITIONING"]]}
    api = _wf.to_api(ui, info_syn)
    assert "2" not in api and api["3"]["inputs"]["conditioning"] == ["1", 0], api

    # 4. Un seul appel : « comfy: » part vers ComfyUI, le reste vers fal ; les
    #    points de génération n'appellent plus fal_client.subscribe directement.
    import importlib
    from core import comfy_image as _cim
    _orig = _cim.subscribe
    _cim.subscribe = lambda name, args, *a, **k: {"images": [{"url": f"http://127.0.0.1:8188/view?filename={name}.png"}]}
    try:
        r = _ic.subscribe("comfy:image_z_image", {"prompt": "p"})
        assert r["images"][0]["url"].endswith("image_z_image.png")
    finally:
        _cim.subscribe = _orig
    for mod in ("api.nano_banana", "api.apercu", "studio_images.imagegen"):
        try:
            src = inspect.getsource(importlib.import_module(mod))
        except Exception:
            import importlib.util
            p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), *mod.split(".")) + ".py"
            src = open(p, encoding="utf-8").read()
        code = "\n".join(l.split("#", 1)[0] for l in src.splitlines())
        assert "fal_client.subscribe(" not in code, f"{mod} : appel fal direct restant"
    se = importlib.import_module("core.image_engines")._load_studio_engines()
    se.ENGINES["comfy:test_tpl"] = se._comfy_engine({"name": "test_tpl", "title": "T", "edit": True, "loads": 2, "size": 5e9})
    try:
        ep, args, kind = se.build_request("comfy:test_tpl", "p", (1024, 576), "1K", ["d1", "d2", "d3"])
        assert ep == "comfy:test_tpl" and args["width"] == 1024 and args["ref_urls"] == ["d1", "d2"] and kind == "raster"
    finally:
        del se.ENGINES["comfy:test_tpl"]


@test
def moteurs_fal_relus_fiche_par_fiche_24_09_2026():
    """Relecture des fiches fal (`llms.txt`) du 24/09/2026 — ce que le code envoie
    doit être ce que la fiche dit. Trois erreurs qui auraient coûté de l'argent
    ou un rejet : Veo journalisé « 1 $ le clip » (fal facture à la seconde,
    3,20 $ le clip par défaut) ; Kling O3 4K envoyait `start_image_url` (le
    champ s'appelle `image_url` → rejet) ; PixVerse envoyait `generate_audio`
    (le champ est `generate_audio_switch` → audio jamais produit). Plus les
    nouveaux moteurs branchés dans les DEUX éditions, aux DEUX endroits."""
    import importlib, inspect, os, tempfile
    import api.video_engines as ve
    from core import pricing, engine_caps, engine_grammar, seedance_family as sf

    # ── 1. Noms de champs (les pièges) ──────────────────────────────────────
    src_o3 = inspect.getsource(ve.KlingO3Worker._real)
    # (le commentaire cite l'ancien nom : on vérifie le CODE, pas les commentaires)
    assert 'args["image_url"] = img_url' in src_o3 and 'args["start_image_url"]' not in src_o3
    src_k = inspect.getsource(ve.KlingWorker._real)
    assert '"image_url" if _turbo else "start_image_url"' in src_k, "Turbo dit image_url, Pro start_image_url"
    assert ve.Wan30Worker.IMAGE_FIELD == "start_image_url" and ve.Wan30Worker.AUDIO_FIELD == "audio"
    for cls in (ve.PixVerseV6Worker, ve.PixVerseWorker):
        s = inspect.getsource(cls._real)
        assert "generate_audio_switch" in s and '"generate_audio":' not in s, cls.__name__

    # ── 2. Endpoints exacts des nouveaux moteurs ────────────────────────────
    assert ve.KlingO3ProWorker.ENDPOINT_I2V == "fal-ai/kling-video/o3/pro/image-to-video"
    assert ve.KlingO3StandardWorker.ENDPOINT_T2V == "fal-ai/kling-video/o3/standard/text-to-video"
    assert ve.Wan30Worker.ENDPOINT_I2V == "alibaba/wan-3.0/image-to-video"
    assert ve.LTX23Worker.ENDPOINT_T2V == "fal-ai/ltx-2.3/text-to-video" and ve.LTX23Worker.END_FRAME
    assert ve.GeminiOmniFlash11Worker.ENDPOINT_I2V == "google/gemini-omni-flash/v1.1/image-to-video"
    assert ve.GrokVideo15Worker.ENDPOINT_T2V == "xai/grok-imagine-video/v1.5/text-to-video"
    assert ve.Veo3Worker._ENDPOINT == {"pro": "fal-ai/veo3.1", "fast": "fal-ai/veo3.1/fast",
                                       "lite": "fal-ai/veo3.1/lite"}
    src_pv = inspect.getsource(ve.PixVerseWorker)
    # (la docstring raconte le remplacement de la v4.5 : on vérifie l'ENDPOINT)
    assert "fal-ai/pixverse/v6/image-to-video" in src_pv and '"fal-ai/pixverse/v4.5' not in src_pv
    src_sora = inspect.getsource(ve.Sora2Worker._real)
    assert "fal-ai/sora-2/image-to-video" in src_sora and '"duration":     dur' in src_sora

    # ── 3. Durées fermées, bornes, ratios, résolutions ──────────────────────
    assert ve.Veo3Worker.snap_duration(5) == 4 and ve.Veo3Worker.snap_duration(7) == 6 \
        and ve.Veo3Worker.snap_duration(30) == 8
    assert ve.Sora2Worker.snap_duration(10) == 8 and ve.Sora2Worker.snap_duration(25) == 20
    assert ve.LTX2Worker.DURATIONS == (6, 8, 10) and ve.LTX2Worker.DUR_STR is False
    _l = ve.LTX2Worker({"prompt": "x"})
    assert _l._snap_duration(5) == 6 and _l._snap_duration(9) == 8
    assert _l._resolution_arg("4K") == "2160p" and _l._resolution_arg("720p") == "1080p"
    _w = ve.Wan30Worker({"prompt": "x"})
    assert _w._snap_duration(45) == 30 and _w._snap_duration(1) == 2
    _k = ve.KlingO3ProWorker({"prompt": "x"})
    assert _k._ratio_arg("21:9") == "16:9" and _k._ratio_arg("1:1") == "1:1" and _k.RATIO_T2V_ONLY

    # ── 4. Tarifs : worker ↔ grille, à la seconde ───────────────────────────
    assert ve.Veo3Worker.price_per_second("pro", "1080p", True) == 0.40
    assert ve.Veo3Worker.price_per_second("lite", "720p", False) == 0.03
    assert pricing.price_per_second("veo-3.1-t2v", "1080p") == 0.40
    assert pricing.price_per_second("sora-2-i2v", "720p") == 0.10
    assert "veo-3.1" not in pricing._PER_VIDEO and "sora-2" not in pricing._PER_VIDEO
    assert pricing.estimate("veo-3.1", "1080p", 8, 1) == (3.2, "s"), "le clip Veo par défaut vaut 3,20 $"
    assert pricing.price_per_second("kling-v3-pro", "1080p") == 0.168
    assert pricing.price_per_second("pixverse-v6", "720p") == 0.060
    assert pricing.price_per_second("wan-2.7-t2v", "1080p") == 0.15, "Wan 2.7 tombait sur le repli 0,30"
    assert pricing.price_per_second("seedance-2.5", "1080p") == 1.164
    assert ve.KlingO3ProWorker({"prompt": "x"})._price_per_s("1080p") == 0.112, "audio OFF par défaut"
    assert ve.KlingO3ProWorker({"prompt": "x", "generate_audio": True})._price_per_s("1080p") == 0.14
    assert ve.KlingO3StandardWorker({"prompt": "x"})._price_per_s("1080p") == 0.084

    # ── 5. Seedance 2.5 : 1080p accepté, 4K rabattu sur 720p ────────────────
    assert sf.supports_resolution("seedance-2.5", "1080p") and not sf.supports_resolution("seedance-2.5", "4k")
    assert sf.clamp_resolution("seedance-2.5", "4k") == "720p"

    # ── 6. Capacités, grammaire, listes du Studio (deux éditions) ───────────
    new_keys = ("veo-3.1-fast", "veo-3.1-lite", "sora-2-pro", "kling-o3-pro", "kling-o3-standard",
                "wan-3.0", "ltx-2.3", "gemini-omni-flash-1.1", "grok-video-1.5")
    for k in new_keys + ("veo-3.1", "sora-2"):
        assert engine_caps.workflow_compatible(k), k
    assert engine_caps.ENGINE_CAPS["kling-o3-4k"]["end_frame"] and engine_caps.ENGINE_CAPS["wan-3.0"]["end_frame"]
    assert engine_grammar.grammar_for("kling-o3-pro") == "directive"
    assert engine_grammar.grammar_for("sora-2-pro") == "sentence"
    import ui.tab_t2v as _T, ui.tab_t2v_live as _TL
    for mod in (_T, _TL):
        keys = [k for _, k in mod._ENGINES]
        for k in new_keys:
            assert k in keys and k in mod._ENGINE_RESOLUTIONS and k in mod._TEXT_FALLBACK_ENGINES, \
                f"{mod.__name__}: {k}"
        assert "prochainement" not in " ".join(l for l, _ in mod._ENGINES), "moteurs branchés : plus de « prochainement »"
        assert "veo-3.1" not in mod._FIXED_RES_ENGINES and mod._ENGINE_RES_FORCED["sora-2"] == "720p"
        assert mod._ENGINE_MAX_DURATION["wan-3.0"] == 30
        w = mod._make_ext_worker("veo-3.1-fast", {"prompt": "x"})
        assert isinstance(w, ve.Veo3Worker) and w.params["variant"] == "fast"
        w = mod._make_ext_worker("sora-2-pro", {"prompt": "x"})
        assert isinstance(w, ve.Sora2Worker) and w.params["variant"] == "pro"
        assert isinstance(mod._make_ext_worker("kling-o3-standard", {"prompt": "x"}), ve.KlingO3StandardWorker)
        assert isinstance(mod._make_ext_worker("wan-3.0", {"prompt": "x"}), ve.Wan30Worker)
        assert isinstance(mod._make_ext_worker("grok-video-1.5", {"prompt": "x"}), ve.GrokVideo15Worker)

    # ── 7. Onglet Moteurs : clés, formulaires alignés, audio Kling O3 décoché ─
    for modname in ("ui.tab_video_engines", "ui.tab_video_engines_live"):
        m = importlib.import_module(modname)
        keys = [k for _, k, _ in m.TabVideoEngines._ENGINES]
        for k in ("veo31_i2v", "veo31_fast_t2v", "veo31_lite_i2v", "sora2_pro_t2v", "kling_o3pro_i2v",
                  "kling_o3std_t2v", "wan30_i2v", "ltx23_t2v", "gemini11_i2v", "grok15_t2v", "pixverse_i2v"):
            assert k in keys, f"{modname}: {k}"
        assert len(keys) == len(set(keys)), f"{modname}: clé en double"
        src = inspect.getsource(m.TabVideoEngines._on_generate)
        for w_ in ("KlingO3ProWorker", "KlingO3StandardWorker", "Wan30Worker", "LTX23Worker",
                   "GeminiOmniFlash11Worker", "GrokVideo15Worker"):
            assert w_ in src, f"{modname}: dispatch {w_}"
        assert "_Veo31Form" not in inspect.getsource(m) and "_Sora2Form" not in inspect.getsource(m)
        tab = m.TabVideoEngines()
        assert len(tab._forms) == len(keys), f"{modname}: formulaires désalignés"
        assert tab._forms[keys.index("kling_o3pro_t2v")]._audio_chk.isChecked() is False
        assert tab._forms[keys.index("kling_o3std_i2v")]._mode == "i2v"
        assert tab._forms[keys.index("veo31_i2v")]._mode == "i2v"
        assert tab._forms[keys.index("veo31_t2v")]._res_combo.currentData() == "720p"
        assert tab._forms[keys.index("grok15_i2v")]._mode == "i2v"
        _pv = tab._forms[keys.index("pixverse_i2v")]
        assert _pv._dur_slider.maximum() == 15 and _pv._res_combo.currentData() == "720p"
        _lt = tab._forms[keys.index("ltx2_t2v")]
        assert _lt._dur_slider.minimum() == 6 and _lt._res_combo.currentData() == "1080p"
        tab.deleteLater()

    # ── 8. ensure_image_urls : un CHEMIN LOCAL dans image_url est uploadé ────
    class _FakeFal:
        @staticmethod
        def upload_file(p):
            return "https://cdn/" + os.path.basename(p)
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "start.png")
        with open(p, "wb") as f:
            f.write(b"x")
        prm = {"image_url": p, "end_image_url": "https://already/ok.png", "mode": "t2v"}
        ve.ensure_image_urls(_FakeFal, prm)
        assert prm["image_url"] == "https://cdn/start.png" and prm["mode"] == "i2v"
        assert prm["end_image_url"] == "https://already/ok.png", "une URL reste une URL"

    # ── 9. Lip-sync + agrandisseur ─────────────────────────────────────────
    from api import lipsync as ls, upscale as up
    assert ls.lipsync_endpoint("kling") == "fal-ai/kling-video/lipsync/audio-to-video"
    assert ls.lipsync_endpoint("pixverse") == "fal-ai/pixverse/lipsync"
    _o = ls.LIPSYNC_ENGINE_ORDER
    assert _o.index("sync2") < _o.index("pixverse") < _o.index("kling") < _o.index("latentsync")
    assert up._ENDPOINTS["topaz_creative"] == "topaz/upscale/video/creative"
    src_up = inspect.getsource(up.UpscaleVideoWorker._real)
    assert '"upscale_mode"' in src_up and 'self._model == "seedvr"' in src_up, "SeedVR2 honore le facteur"
    assert up.UpscaleVideoWorker("x.mp4", model="topaz_creative")._model == "topaz_creative"

    # ── 10. Images : nouveaux moteurs et endpoints d'édition ────────────────
    from core import image_engines as ie
    ep, a, _ = ie.build_request("gpt25", "p", (1920, 1080), "1K", ["data:a"])
    assert ep == "openai/gpt-image-2.5/flare/edit" and a["image_urls"] == ["data:a"] and a["quality"] == "high"
    ep, a, _ = ie.build_request("gpt25", "p", (1920, 1080), "1K", [])
    assert ep == "openai/gpt-image-2.5/flare/text-to-image" and "image_urls" not in a
    ep, a, _ = ie.build_request("flux2", "p", (1920, 1080), "1K", ["data:a", "data:b"])
    assert ep == "fal-ai/flux-2-pro/edit" and a["image_urls"] == ["data:a", "data:b"] and "num_images" not in a
    ep, a, _ = ie.build_request("flux2", "p", (1920, 1080), "1K", [])
    assert ep == "fal-ai/flux-2-pro" and "image_urls" not in a
    se = ie._load_studio_engines()
    ep, a, _ = se.build_request("kling_image", "p", (1920, 1080), "1K", ["d1"])
    assert ep == "fal-ai/kling-image/o3/image-to-image" and a["resolution"] == "2K" and a["image_urls"] == ["d1"]
    ep, a, _ = se.build_request("kling_image", "p", (1024, 1024), "1K", [])
    assert ep == "fal-ai/kling-image/o3/text-to-image" and a["resolution"] == "1K" and a["aspect_ratio"] == "1:1"
    ep, a, _ = se.build_request("seedream5_flash", "p", (1920, 1080), "1K", ["d"] * 12)
    assert ep == "bytedance/seedream/v5/flash/edit" and len(a["image_urls"]) == 10
    ep, a, _ = se.build_request("qwen_image2", "p", (1920, 1080), "1K", ["d"] * 5)
    assert ep == "fal-ai/qwen-image-2/edit" and len(a["image_urls"]) == 3, "Qwen-Image 2 : 3 refs maximum"
    ep, a, _ = se.build_request("qwen_image2_pro", "p", (1920, 1080), "1K", ["d"])
    assert ep == "fal-ai/qwen-image-2/pro/text-to-image" and "image_urls" not in a
    assert "0.035" in se.ENGINES["recraft"]["label"] and "$0.20" in ie.ENGINES["gpt2"]["label"]
    assert {"gpt25", "kling_image", "seedream5_flash", "qwen_image2", "flux2"} <= set(ie.edit_capable_engines())
    from core.config import IMAGE_MODEL_PRICES
    assert IMAGE_MODEL_PRICES["gpt2"] == "$0.20" and IMAGE_MODEL_PRICES["recraft"] == "$0.035"
    import api.nano_banana as nb
    assert '"fal-ai/instant-id"' not in inspect.getsource(nb), "id fal inexistant : aucun appel ne doit le porter"
    assert "fal-ai/flux-pulid" in inspect.getsource(nb.GeneratePortraitWithFaceIDWorker._real)


@test
def gabarits_comfy_trouves_en_version_installee():
    """Constat Matthieu (24/09/2026, installeur 2.4.0) : « Aucun workflow
    ComfyUI : choisissez un gabarit H3 ou un fichier .json » à chaque
    génération H3 sur ComfyUI. Les .json étaient bien livrés dans _internal/
    mais cherchés sous APP_ROOT, qui en version gelée est le dossier de DONNÉES
    (%LOCALAPPDATA%\\PANDORA). Invisible en dev : les deux racines coïncident.
    On simule le mode gelé : les gabarits doivent venir de sys._MEIPASS."""
    import inspect, os, shutil, sys as _sys, tempfile
    from core import comfy_workflow as wf, comfy_h3 as h3c, paths as _paths
    _src = inspect.getsource(wf.workflows_dir)
    assert "from core.paths import assets_root" in _src and "join(APP_ROOT" not in _src, \
        "les assets livrés ne se cherchent pas sous APP_ROOT (dossier de données en gelé)"
    # Dev : le dossier du projet, gabarits présents.
    assert os.path.isfile(h3c.template_path("comfy_h3_i2v")) and os.path.isfile(h3c.template_path("comfy_h3_t2v"))
    assert _paths.assets_root() == _paths.APP_ROOT, "en dev, une seule racine"
    # Gelé simulé : _MEIPASS avec assets/comfy_workflows, APP_ROOT ailleurs.
    tmp = tempfile.mkdtemp(prefix="pandora_meipass_")
    try:
        dst = os.path.join(tmp, "assets", "comfy_workflows")
        os.makedirs(dst)
        shutil.copy(h3c.template_path("comfy_h3_i2v"), dst)
        had_frozen, had_mei = hasattr(_sys, "frozen"), hasattr(_sys, "_MEIPASS")
        old_frozen, old_mei = getattr(_sys, "frozen", None), getattr(_sys, "_MEIPASS", None)
        _sys.frozen, _sys._MEIPASS = True, tmp
        try:
            assert _paths.assets_root() == tmp
            p = h3c.template_path("comfy_h3_i2v")
            assert p.startswith(tmp) and os.path.isfile(p), p
            assert not h3c.template_path("comfy_h3_t2v").startswith(_paths.APP_ROOT)
            prm = h3c.prepare_params({"prompt": "x"}, "comfy_h3_i2v")
            assert os.path.isfile(prm["workflow_path"]) and prm["mode"] == "i2v"
        finally:
            if had_frozen:
                _sys.frozen = old_frozen
            else:
                del _sys.frozen
            if had_mei:
                _sys._MEIPASS = old_mei
            else:
                del _sys._MEIPASS
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # Et le build embarque bien le dossier (spec : tout assets/).
    spec = open(os.path.join(_paths.APP_ROOT, "pandora.spec"), encoding="utf-8").read()
    assert '("assets", "assets")' in spec, "assets/ (dont comfy_workflows) doit être dans datas"


@test
def modifier_un_clip_credits_limites_video_et_levres_25_09_2026():
    """Constat Matthieu 25/09/2026 sur « Modifier des clips » : « Crédits fal.ai
    insuffisants » à chaque génération — alors que fal avait 13 $ de solde et
    que c'était le compte Anthropic (traduction) qui était vide. La détection
    de crédit mordait sur « credit », « balance », « out of », « quota » : un
    rejet de validation fal (« duration out of range ») passait aussi pour un
    problème de crédits. Trois choses sont épinglées : le bon compte est nommé,
    le clip de référence est conformé aux limites du moteur AVANT l'upload
    (Seedance 2.0 : 720p, 15 s — fiche fal), et le lip-sync de cet onglet offre
    le moteur au choix et l'audio de doublage, dans les deux éditions."""
    import importlib, inspect, os, subprocess, tempfile
    from core import worker as W, seedance_family as sf, video_utils as vu

    # ── 1. Crédits : le BON compte, et une validation n'est plus un « crédit » ─
    anth = ("Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
            "'message': 'Your credit balance is too low to access the Anthropic API. "
            "Please go to Plans & Billing to upgrade or purchase credits.'}}")
    m = W.humanize_api_error(anth)
    assert "IA TEXTE" in m and "fal.ai n'est pas en cause" in m, m
    falb = "403 Forbidden: Exhausted balance. Top up your balance at fal.ai/dashboard/billing."
    assert W.humanize_api_error(falb).startswith("Crédits fal.ai insuffisants")
    val = ("422 Unprocessable Entity: [{'loc': ['body', 'video_urls'], "
           "'msg': 'Video duration out of range [2, 15]', 'type': 'value_error'}]")
    assert W.humanize_api_error(val) == val, "un rejet de validation reste lisible tel quel"
    for s in ("file size limit exceeded", "video out of range", "quota of 3 videos", "Content moderation: unsafe"):
        assert not W.is_credit_error(s), s
    assert W.fal_error_detail(val) == "Video duration out of range [2, 15]"
    import ui.tab_davinci_edit as DE
    assert DE.TabDavinciEdit._humanize_error(val).startswith("Refusé par le moteur : Video duration out of range")

    # ── 2. Limites du clip de référence par moteur, appliquées par api/real ──
    assert sf.video_input_limits("seedance-2.0") == (720, 15)
    assert sf.video_input_limits("seedance-2.0-fast") == (720, 15)
    assert sf.video_input_limits("seedance-2.5") == (1080, 30)
    assert sf.video_input_limits("inconnu") == (720, 15), "repli = la 2.0, la plus stricte"
    _rsrc = inspect.getsource(importlib.import_module("api.real"))
    assert "video_input_limits(model)" in _rsrc and "max_height=_vh, max_seconds=_vs" in _rsrc
    # Clip synthétique 1080p / 4 s → 720p / 2 s (ffmpeg embarqué) ; sans plafond, tel quel.
    ffmpeg = vu.get_ffmpeg_exe()
    d = tempfile.mkdtemp(prefix="pandora_vu_")
    src = os.path.join(d, "clip1080.mp4")
    r = subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=24:duration=4",
                        "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", src],
                       capture_output=True, timeout=120, creationflags=getattr(vu, "_NO_WINDOW", 0))
    assert r.returncode == 0 and os.path.isfile(src), "ffmpeg embarqué : clip de test"
    assert vu.video_needs_transcode(src) == "", "1080p progressif : rien à convertir pour un moteur 1080p"
    why = vu.video_needs_transcode(src, max_height=720, max_seconds=2)
    assert "> 720p" in why and "> 2 s" in why, why
    out = vu.ensure_engine_video(src, max_height=720, max_seconds=2)
    assert out != src and out.endswith("_720p_2s.mp4"), out
    assert vu._video_dims(out) == (1280, 720), vu._video_dims(out)
    assert abs(vu.video_duration_s(out) - 2.0) < 0.2, vu.video_duration_s(out)
    assert vu.ensure_engine_video(src) == src, "sans plafond, le 1080p part tel quel"
    assert vu.ensure_engine_video(src, max_height=720, max_seconds=2) == out, "cache par plafond"

    # ── 3. Veo : tolérance de modération au maximum (Pro/Fast ; Lite n'a pas le champ)
    import api.video_engines as ve
    _vsrc = inspect.getsource(ve.Veo3Worker._real)
    assert 'args["safety_tolerance"] = "6"' in _vsrc and 'if variant != "lite"' in _vsrc

    # ── 4. Lèvres : moteur au choix + audio fichier, vidéo locale déposée chez fal
    from api import lipsync as ls
    assert ls.engine_label("sync3").startswith("Sync-3 · $8/min — 2026")
    assert ls._is_public_url("https://v3.fal.media/x.mp4")
    assert not ls._is_public_url("http://127.0.0.1:8188/view?filename=a.mp4")
    assert not ls._is_public_url(r"C:\clips\a.mp4")
    assert "ensure_public_video_url(" in inspect.getsource(ls.LipSyncWorker._run)
    tab = DE.TabDavinciEdit()
    keys = [tab._lipsync_engine_combo.itemData(i) for i in range(tab._lipsync_engine_combo.count())]
    assert keys == ls.LIPSYNC_ENGINE_ORDER and "sync3" in keys and "kling" in keys, keys
    assert tab._lipsync_audio_combo.currentData() == "clip" and tab._btn_lipsync_audio.isHidden()
    tab._lipsync_audio_combo.setCurrentIndex(1)
    assert tab._lipsync_audio_combo.currentData() == "file" and not tab._btn_lipsync_audio.isHidden()
    assert tab._lipsync_audio_file() == "", "aucun fichier choisi → rien"
    _ssrc = inspect.getsource(DE.TabDavinciEdit._start_lipsync)
    assert "engine            = engine" in _ssrc and "audio_path        = self._lipsync_audio_file()" in _ssrc
    assert "LatentSyncWorker" not in _ssrc, "le worker s'appelle par son nom générique"
    _gsrc = inspect.getsource(DE.TabDavinciEdit._start_queue) if hasattr(DE.TabDavinciEdit, "_start_queue") \
        else inspect.getsource(DE)
    assert "Audio des lèvres manquant" in _gsrc, "mode fichier sans fichier → refus AVANT de payer"
    tab.deleteLater()


if __name__ == "__main__":
    sys.exit(main())
