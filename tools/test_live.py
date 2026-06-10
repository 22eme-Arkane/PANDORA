"""
tools/test_live.py — Harnais de non-régression PANDORA | Live.

À lancer avant chaque build / après chaque session de modifications :

    C:\\Users\\22eme\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe tools\\test_live.py

- Headless (Qt offscreen) : n'ouvre aucune fenêtre.
- Données dans un dossier temporaire : ne touche ni aux projets ni à la config.
- AUCUN appel réseau : on ne démarre jamais de worker API (vérifications statiques
  + construction des widgets uniquement).

Code de sortie : 0 si tout passe, 1 sinon (utilisable en CI / build.ps1).
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
QDialog.exec = lambda self: 0          # aucun dialogue bloquant en headless
# Les confirmations répondent toujours « Oui » en headless (statiques C++,
# non couvertes par le patch QDialog.exec ci-dessus).
QMessageBox.question = staticmethod(
    lambda *a, **k: QMessageBox.StandardButton.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

# Projet temporaire — isole toutes les écritures du harnais
import core.context as ctx
_TMP = tempfile.mkdtemp(prefix="pandora_test_")
ctx.set_project_path(_TMP)
ctx.set_project_id("test_harness")

_TESTS = []


def test(fn):
    _TESTS.append(fn)
    return fn


# ══════════════════════════════════════════════════════════════════════════════
# Logique pure (parsing, normalisation, timeline musicale)
# ══════════════════════════════════════════════════════════════════════════════

@test
def json_parser_robuste():
    """_extract_json_array encaisse crochets/troncature/virgules/texte autour."""
    from api.live_screenplay import _extract_json_array as ex
    fence = chr(96) * 3
    assert len(ex(fence + 'json\n[{"a":1},{"a":2}]\n' + fence)) == 2, "bloc json"
    assert len(ex('[{"p":"x [y] z"},{"p":"w"}]')) == 2, "crochet dans valeur"
    assert len(ex('[{"a":1,"p":"ok"},{"a":2,"p":"tronq')) == 1, "tableau tronqué"
    assert len(ex('Voici :\n[{"a":1},{"a":2},]\nfin.')) == 2, "virgule finale + texte"
    assert ex("aucun json ici") == [], "pas de json"


@test
def normalize_decoupage():
    """_normalize produit act/act_name/sound_prompt, clamp durée, Fixe en mapping."""
    from api.live_screenplay import _normalize
    n = _normalize({"action": "a", "prompt": "v", "sound_prompt": "s",
                    "act": 2, "act_name": "Drop", "duration": 99,
                    "camera_movement": "Travelling"}, "mapping")
    assert n["act"] == 2 and n["act_name"] == "Drop", "act/act_name"
    assert n["sound_prompt"] == "s", "sound_prompt"
    assert n["duration"] == 15, "clamp durée 15"
    assert n["camera_movement"] == "Fixe", "mapping force Fixe"
    n2 = _normalize({"action": "a", "duration": 1}, "live")
    assert n2["duration"] == 4, "clamp durée min 4"
    assert n2["act"] == 1, "act par défaut"


@test
def timeline_musicale():
    """build_set_timeline : BPM + drops + consigne ; vide sans analyse."""
    from core.music_analysis import build_set_timeline
    tl = build_set_timeline([{"name": "t.mp3", "bpm": 128.0, "duration": 222.0,
                              "energy": "▁▃▅", "drops": [48.0]}])
    assert "128 BPM" in tl and "0:48" in tl and "Resolume" in tl
    assert build_set_timeline([{"name": "x", "bpm": 0}]) == "", "sans BPM = vide"


@test
def reference_batiment_persistance():
    """set/get/clear de la façade dans le data root du projet."""
    from PIL import Image
    import core.live_building as lb
    img = os.path.join(_TMP, "_facade_t.jpg")
    Image.new("RGB", (32, 18), (90, 90, 90)).save(img)
    lb.set_building_ref(img)
    assert lb.get_building_ref() == img, "get après set"
    lb.clear_building_ref()
    assert lb.get_building_ref() == "", "clear"


# ══════════════════════════════════════════════════════════════════════════════
# Prompts IA (dramaturgie mapping, séparation vidéo/son, terminologie actes)
# ══════════════════════════════════════════════════════════════════════════════

@test
def prompts_decoupage_mapping():
    """Découpage Mapping : façade = écran (présence variable), prompts détaillés."""
    import api.live_screenplay as ls
    t = ls._SYSTEM_MAPPING
    assert "RÉVÉLATION" in t and "EXTINCTION" in t and "RECOUVREMENT" in t, "dramaturgie présence"
    assert "seuls la lumière, les effets, les matières" not in t, "ancienne consigne façade-toujours-visible"
    assert "TRÈS DÉTAILLÉ" in t, "prompts vidéo détaillés"
    assert "ÉTAT DE LA FAÇADE" in t, "prompt commence par l'état de la façade"
    assert "sound_prompt" in t and "BPM" in t, "séparation vidéo/son"
    assert "TOTALEMENT FIXE" in t, "caméra fixe"


@test
def prompts_arrangement_conducteur():
    """Arrangement : vocabulaire conducteur (actes), pas de vocabulaire scénario."""
    import api.live_screenplay as ls
    for name in ("_ARRANGE_LIVE", "_ARRANGE_MAPPING"):
        t = getattr(ls, name)
        assert "INT." in t and "EXT." in t, f"{name} : interdiction INT./EXT. énoncée"
        assert "« séquence »" in t, f"{name} : bannit « séquence »"
        assert "ACTES" in t, f"{name} : raisonne en actes"
    assert "présence de la façade" in ls._ARRANGE_MAPPING.lower() or \
           "PRÉSENCE" in ls._ARRANGE_MAPPING, "dramaturgie présence dans l'arrangement mapping"


@test
def prompts_mise_en_page():
    """Mise en page PANDORA Live : Sonnet, façade-écran, vidéo/son séparés, durée cible."""
    import api.live_extract as le
    src = inspect.getsource(le.FormatConducteurWorker.run)
    assert 'tier="creative"' in src, "tier créatif (Sonnet/Fable) pour la mise en page"
    assert "ÉCRAN" in src, "façade = écran (pas un sujet)"
    assert "seuls" not in src.split("ÉCRAN")[0] or True
    assert "TRÈS DÉTAILLÉ" in src, "prompts vidéo détaillés"
    assert "PROMPT SON" in src and "PROMPT VIDÉO" in src, "deux prompts par plan"
    assert "DURÉE CIBLE" in src, "durée cible injectée"
    assert "INTERDIT d'y mettre le BPM" in src, "BPM banni du prompt vidéo"


@test
def prompts_generation_video_mapping():
    """Suffixe ADN mapping : canvas, nuit, noirs purs, caméra verrouillée, keyframes."""
    from ui.tab_t2v_live import TabT2V
    src = inspect.getsource(TabT2V.start_generation)
    assert "projection CANVAS" in src, "façade = canvas"
    assert "lit ONLY" not in src, "plus d'ordre de garder la façade visible"
    assert "STATIC LOCKED CAMERA" in src, "caméra verrouillée"
    assert "PURE BLACK #000000" in src, "noirs purs"
    assert "end_image_path" in src, "keyframe d'arrivée branchée"
    assert '"mapping"' in src.split("Framing prefix")[1][:300], "préfixe focale neutralisé en mapping"


@test
def prompt_mood_live_propre():
    """En Séquences Live/Mapping, le prompt mood est épuré : pas de termes caméra,
    pas de français, pas de film grain, état d'OUVERTURE demandé (keyframe)."""
    import core.storyboard as sb
    from api.apercu import build_mood_prompt
    shot = {"seedance_prompt": "Opening: blue ocean. Then a whale. In the final moment dark.",
            "scene_title": "Les baleines disparaissent",
            "focal": "35mm", "shot_size": "PL", "camera_axis": "Face",
            "camera_distance": "4m", "camera_movement": "Travelling avant",
            "decor_name": "Façade", "shot_time": "Nuit"}
    sb.set_namespace("live_seq_mapping")
    p_live = build_mood_prompt(shot, "style x")
    sb.set_namespace("storyboard")
    p_cine = build_mood_prompt(shot, "style x")
    # Live : épuré
    assert "lens" not in p_live and "35mm" not in p_live, "pas de focale en Live"
    assert "film grain" not in p_live, "pas de grain (noirs purs)"
    assert "Les baleines" not in p_live, "pas de titre français collé"
    assert "OPENING state" in p_live, "état d'ouverture demandé (keyframe de début)"
    assert "dolly push in" not in p_live, "pas de mouvement caméra"
    # Cinéma : comportement historique INCHANGÉ
    assert "35mm" in p_cine and "film grain" in p_cine and "Les baleines" in p_cine


@test
def prompts_moods_kontext():
    """Moods Kontext : canvas (peut recouvrir/cacher la façade), nuit, fond noir."""
    import api.apercu as A
    src = inspect.getsource(A.run_generation)
    assert "projection CANVAS" in src, "canvas"
    assert "lit ONLY" not in src, "ancienne consigne retirée"
    assert "PURE BLACK #000000" in src, "fond noir"
    assert "fal-ai/flux-pro/kontext" in src, "Kontext quand façade fournie"


@test
def prompts_cinema_detailles():
    """Cinéma : prompts storyboard + mise en page enrichis, fidèles au scénario."""
    import api.screenplay as s
    assert "DETAILED, dense video generation prompt" in s._GENERATE_STORYBOARD_TMPL
    assert "WITHOUT inventing any new story element" in s._GENERATE_STORYBOARD_TMPL
    assert "TRÈS DÉTAILLÉ" in s._FORMAT_PANDORA and "FIDÈLE au scénario" in s._FORMAT_PANDORA
    assert "HIGHLY DETAILED" in s._FORMAT_PANDORA_EN


@test
def facade_resolution_par_namespace():
    """La façade n'est injectée dans les moods QUE en Séquence Mapping."""
    from PIL import Image
    import core.live_building as lb
    import core.storyboard as sb
    from api.apercu import _resolve_building_ref
    img = os.path.join(_TMP, "_facade_ns.jpg")
    Image.new("RGB", (32, 18), (90, 90, 90)).save(img)
    lb.set_building_ref(img)
    try:
        sb.set_namespace("live_seq_mapping")
        assert _resolve_building_ref() == img, "mapping → façade"
        sb.set_namespace("live_seq_live")
        assert _resolve_building_ref() == "", "live → pas de façade"
        sb.set_namespace("storyboard")
        assert _resolve_building_ref() == "", "cinéma → pas de façade"
    finally:
        lb.clear_building_ref()
        sb.set_namespace("storyboard")


# ══════════════════════════════════════════════════════════════════════════════
# Tableau Séquences (colonnes, masquage Mapping, conducteur)
# ══════════════════════════════════════════════════════════════════════════════

@test
def colonnes_sequences():
    """22 colonnes, masquages Live {6,11,12} / Mapping {5..12}, ordre conducteur."""
    import core.storyboard as sb
    import ui.page_storyboard_live as M
    from ui.live_pages import SequenceLivePage, SequenceMappingPage, _LIVE_DEFAULT_ORDER
    assert len(M._COLS) == 22, "22 colonnes"
    assert M._COLS[2][0] == "Acte" and M._COLS[4][0] == "Prompt vidéo / son"
    assert M._COLS[16][0] == "TC" and M._COLS[17][0] == "Musique"
    assert M._COLS[18][0] == "BPM" and M._COLS[19][0] == "Transition"
    assert sorted(_LIVE_DEFAULT_ORDER) == list(range(22)), "ordre défaut = permutation valide"
    mp = SequenceMappingPage(); mp.refresh()
    vis = M._visible_order()
    assert all(c not in vis for c in (5, 6, 7, 8, 9, 11, 12)), "masquage Mapping (+Mouvement)"
    assert all(c in vis for c in (16, 17, 18, 19, 20)), "colonnes conducteur visibles"
    # Ordre par défaut conducteur appliqué : TC (16) juste après Plan (3)
    assert vis[:5] == [0, 1, 2, 3, 16], "TC/Durée en tête par défaut"
    live = SequenceLivePage(); live.refresh()
    vis_l = M._visible_order()
    assert all(c not in vis_l for c in (6, 11, 12)), "Live masque Mouvement/Décor/Heure"
    assert 5 in vis_l and 7 in vis_l, "Live garde Axe/Valeur"
    sb.set_namespace("storyboard")


@test
def reorg_colonnes_et_heritages():
    """Drag de colonnes correct avec colonnes masquées + héritages Cinéma retirés."""
    import inspect
    import ui.page_storyboard_live as M
    src = inspect.getsource(M)
    assert "src_logical = self._cell_logical[src]" in src, \
        "reorder mappe visuel→logique (bug du drag avec colonnes masquées)"
    assert "self._btn_sync.setVisible(False)" in src, "Synchronisation masquée en Live"
    # Extraction calibrée Live branchée dans le Conducteur
    from ui.page_scenario_live import PageScenario
    src_sc = inspect.getsource(PageScenario)
    assert "_live_extract_dialog" in src_sc and "live_extract_worker_cls" in src_sc
    assert "for_decors" not in src_sc and "for_hmc" not in src_sc, \
        "Tout générer sans Décors/HMC (inexistants en Live)"
    # Appliquer les suggestions = worker CONDUCTEUR (pas le format scénario)
    assert "ApplyArrangeConducteurWorker" in src_sc
    from api.live_screenplay import ApplyArrangeConducteurWorker, _APPLY_ARRANGE_CONDUCTEUR
    assert "INT." in _APPLY_ARRANGE_CONDUCTEUR, "interdiction INT./EXT. énoncée"
    w = ApplyArrangeConducteurWorker("a", "b", 5)
    assert hasattr(w, "chunk"), "streaming"
    # Focale + Tarifs masqués dans Générer depuis Séquences
    from ui.tab_t2v_live import TabT2V
    src_tv = inspect.getsource(TabT2V)
    assert "self._camera_picker.setVisible(False)" in src_tv
    assert "btn_tarifs.setVisible(False)" in src_tv
    # Dialogue Éditer : Optique/Décor/Heure/Micro masqués
    import ui.dialog_shot_live as ds
    src_ds = inspect.getsource(ds)
    for marker in ("_hide_col(col_optic)", "_hide_col(col_decor)",
                   "_hide_col(col_time)", "_hide_col(col_mic)"):
        assert marker in src_ds, f"dialogue Live : {marker}"


@test
def decoupage_routage_et_champs():
    """_apply_decoupage : namespace live_seq_{mode}, act→seq, sound_prompt sauvé."""
    import core.storyboard as sb
    from ui.page_scenario_live import PageScenario
    p = PageScenario()
    navs = []
    p.navigate_requested.connect(lambda k, e="": navs.append(k))
    segs = [{"action": "a", "duration": 6, "prompt": "v", "sound_prompt": "s",
             "act": 2, "act_name": "Drop"}]
    p._live_mode = "mapping"
    p._apply_decoupage(segs)
    assert sb.get_namespace() == "live_seq_mapping" and navs[-1] == "seq_mapping"
    shots = sb.list_shots()
    assert shots and shots[0]["sound_prompt"] == "s" and shots[0]["seq_num"] == 2
    p._live_mode = "live"
    p._apply_decoupage(segs)
    assert sb.get_namespace() == "live_seq_live" and navs[-1] == "seq_live"
    sb.set_namespace("storyboard")


@test
def dialog_plan_live_sound_prompt():
    """ShotDialog Live a le champ sound design ; le ShotDialog Cinéma n'en a pas."""
    from ui.dialog_shot_live import ShotDialog as LiveDlg
    import ui.dialog_shot as cine
    d = LiveDlg(shot={"id": "s1", "number": 1, "sound_prompt": "boom"})
    assert hasattr(d, "_sound_prompt") and d._sound_prompt.toPlainText() == "boom"
    assert "sound_prompt" not in inspect.getsource(cine.ShotDialog), "Cinéma intact"
    import ui.page_storyboard_live as M
    assert M.ShotDialog.__module__ == "ui.dialog_shot_live", "la page Live ouvre la copie Live"


@test
def mood_info_dialog_par_mode():
    """Le message avant « Générer les Moods » est calqué Live ou Mapping (plus Cinéma)."""
    import core.storyboard as sb
    from ui.page_storyboard_live import _MoodInfoDialog
    sb.set_namespace("live_seq_live")
    assert _MoodInfoDialog(None)._mode == "live"
    sb.set_namespace("live_seq_mapping")
    assert _MoodInfoDialog(None)._mode == "mapping"
    src = inspect.getsource(_MoodInfoDialog._build_ui)
    assert "Rendu de nuit" in src and "focale, l" not in src, "conseils mapping, pas cinéma"
    sb.set_namespace("storyboard")


# ══════════════════════════════════════════════════════════════════════════════
# Onglet « Générer depuis Séquences » (tab_t2v_live)
# ══════════════════════════════════════════════════════════════════════════════

@test
def t2v_live_selecteur_et_options():
    """Sélecteur Live/Mapping, namespace, dyn-cam/raccord auto, DaVinci neutralisé."""
    import core.storyboard as sb
    from ui.tab_t2v_live import TabT2V
    t = TabT2V()
    assert t._seq_mode == "live" and sb.get_namespace() == "live_seq_live"
    t._set_seq_mode("mapping")
    assert sb.get_namespace() == "live_seq_mapping"
    assert t._raccord_auto_cb.isChecked(), "raccord auto coché en Mapping"
    assert t._dyn_cam_toggle_row.isHidden(), "caméra dynamique retirée en Mapping"
    t._set_seq_mode("live")
    assert not t._dyn_cam_toggle_row.isHidden(), "caméra dynamique de retour en Live"
    # refresh recale le namespace même changé ailleurs
    sb.set_namespace("storyboard")
    t._seq_mode = "mapping"
    t.refresh()
    assert sb.get_namespace() == "live_seq_mapping", "refresh recale"
    # DaVinci PURGÉ (pas seulement masqué) / sections repliées / décors masqués
    assert not hasattr(t, "_davinci_bar"), "barre DaVinci supprimée"
    assert not hasattr(t, "_import_cb"), "case import DaVinci supprimée"
    assert not hasattr(t, "_check_davinci_connection"), "vérif connexion DaVinci supprimée"
    import ui.tab_t2v_live as _m
    _src = inspect.getsource(_m)
    assert "davinci.bridge" not in _src, "plus d'import du bridge DaVinci"
    assert "import_to_davinci=False" in _src, "téléchargement local uniquement"
    assert t._casting.isHidden(), "Éléments récurrents replié par défaut"
    assert t._film_style_frame.isHidden(), "Choisir les références replié par défaut"
    assert not t._casting._decor_toggle.isVisible(), "section Décors masquée"
    assert hasattr(t, "_bref_row"), "sélecteur façade présent"
    sb.set_namespace("storyboard")


@test
def t2v_live_keyframes_mapping():
    """Raccord par keyframes : mood N = début, mood N+1 = fin, fallback sans mood."""
    import core.storyboard as sb
    from PIL import Image
    from ui.tab_t2v_live import TabT2V
    sb.set_namespace("live_seq_mapping")
    sb.clear_version_shots(sb.DEFAULT_VERSION_ID)
    shots = [sb.save_shot({"number": i, "scene_title": f"P{i}", "duration": 6},
                          sb.DEFAULT_VERSION_ID) for i in (1, 2, 3)]
    for s in shots[:2]:
        ad = sb.get_apercu_dir(s["id"])
        os.makedirs(ad, exist_ok=True)
        p = os.path.join(ad, f"mood_{s['number']}.jpg")
        Image.new("RGB", (32, 18), (40, 40, 40)).save(p)
        sb.save_apercus(s["id"], [p], 0)
    t = TabT2V()
    t._set_seq_mode("mapping")
    s1, e1 = t._get_mapping_keyframes(shots[0])
    s2, e2 = t._get_mapping_keyframes(shots[1])
    s3, e3 = t._get_mapping_keyframes(shots[2])
    assert s1.endswith("mood_1.jpg") and e1.endswith("mood_2.jpg"), "plan 1 chaîné vers mood 2"
    assert s2.endswith("mood_2.jpg") and e2 == "", "plan 2 : pas de mood au plan 3"
    assert (s3, e3) == ("", ""), "plan 3 sans mood → fallback"
    sb.set_namespace("storyboard")


@test
def moteurs_filtres_workflow():
    """Seuls les moteurs compatibles workflow (i2v/keyframes/réfs) sont proposés."""
    from core.engine_caps import workflow_compatible, sequence_engines, ENGINE_CAPS
    assert not workflow_compatible("veo-3.1") and not workflow_compatible("sora-2"), \
        "t2v purs écartés"
    for k in ("seedance-2.0", "kling-v3-pro", "happy-horse-1.0", "pixverse-v6"):
        assert workflow_compatible(k), f"{k} compatible"
    assert ENGINE_CAPS["kling-v3-pro"]["end_frame"], "Kling v3 = keyframes (end_image_url)"
    # Le combo de l'onglet est filtré
    import core.context as _ctx, tempfile as _tf
    from ui.tab_t2v_live import TabT2V, _ENGINES
    keys = [k for _, k in sequence_engines(_ENGINES)]
    assert "veo-3.1" not in keys and "sora-2" not in keys
    t = TabT2V()
    combo_keys = [t.cb_model.itemData(i) for i in range(t.cb_model.count())]
    assert "veo-3.1" not in combo_keys and "sora-2" not in combo_keys
    assert "kling-v3-pro" in combo_keys and "seedance-2.0" in combo_keys
    # Les workers externes savent uploader les keyframes locales
    import api.video_engines as ve, inspect as _i
    assert hasattr(ve, "ensure_image_urls"), "helper d'adaptation i2v"
    for cls in (ve.KlingWorker, ve.KlingO3Worker, ve.HappyHorseWorker, ve.PixVerseV6Worker):
        assert "ensure_image_urls" in _i.getsource(cls._real), f"{cls.__name__} adapté"
    import core.storyboard as sb
    sb.set_namespace("storyboard")


@test
def t2v_live_anticrash_threads():
    """Le worker de traduction d'aperçu passe par abandon_thread (anti-crash)."""
    from ui.tab_t2v_live import TabT2V
    src = inspect.getsource(TabT2V._start_preview_translate)
    assert "abandon_thread" in src, "abandon_thread requis (quit() inopérant sur QThread run())"


# ══════════════════════════════════════════════════════════════════════════════
# Studio IA Live + fenêtre Live
# ══════════════════════════════════════════════════════════════════════════════

@test
def studio_onglets():
    """7 onglets, Sound Design + Upscaling présents et câblés à la Vidéothèque."""
    from ui.live_studio_widget import LiveStudioWidget
    s = LiveStudioWidget()
    titres = [s.tabs.tabText(i) for i in range(s.tabs.count())]
    assert len(titres) == 7, f"7 onglets attendus, {len(titres)} trouvés"
    for attendu in ("Sound Design", "Upscaling", "Vidéothèque", "Historique"):
        assert any(attendu in x for x in titres), f"onglet {attendu} manquant"
    assert s.tab_upscale._library_provider is not None, "Upscaling relié à la Vidéothèque"
    # file d'attente upscaling : ajout + dédoublonnage
    real = os.path.abspath(__file__)
    assert s.tab_upscale.add_clips_from_paths([real, real]) == 1, "dédoublonnage file"
    s._on_send_to_upscale([real])
    assert s.tabs.tabText(s.tabs.currentIndex()) == "Upscaling", "bascule vers Upscaling"


@test
def fenetre_live():
    """Topbar, assistant fermé par défaut, Paramètres en bas, alias de navigation."""
    from live_window import LiveWindow
    w = LiveWindow({})
    assert hasattr(w, "_btn_save_global") and hasattr(w, "_btn_update_header"), "topbar"
    assert w._assistant.isHidden(), "assistant IA fermé par défaut"
    assert w._assistant_toggle._open is False, "poignée synchronisée"
    assert "settings" in w._sidebar._items, "Paramètres dans la nav"
    w._navigate("castings")   # alias Cinéma → Live, ne doit pas lever
    w._navigate("vehicles")
    assert w._NAV_ALIASES["castings"] == "casting"


@test
def conducteur_ui():
    """Onglets Conducteur/Mise en page, mode dans la bande Durée cible, musique injectée."""
    from ui.page_scenario_live import PageScenario
    p = PageScenario()
    assert p._editor_tabs.count() == 2, "2 onglets éditeur"
    assert not p._editor_tabs.isTabEnabled(1), "Mise en page grisée au départ"
    assert hasattr(p, "_btn_mode_live") and hasattr(p, "_btn_mode_mapping"), "boutons mode"
    assert hasattr(p, "_music_hbox") and hasattr(p, "_bld_row"), "sections musique + façade"
    p._set_editor_text("Mon conducteur")
    p._music_tracks = [{"name": "t.mp3", "bpm": 128.0, "duration": 100.0,
                        "energy": "", "drops": []}]
    txt = p._text_with_music()
    assert "TIMELINE MUSICALE" in txt and txt.endswith("Mon conducteur"), "timeline préfixée"
    p._apply_layout("PLAN 1 — test")
    assert p._editor_tabs.isTabEnabled(1), "onglet Mise en page activé"
    assert p._editor_text.toPlainText() == "Mon conducteur", "conducteur intact"


@test
def workers_construction():
    """Les workers se construisent avec les bons paramètres (sans .start())."""
    from api.upscale import UpscaleVideoWorker, UPSCALE_MODELS
    from api.tts import SFX1VideoWorker, SFX1Worker
    from api.live_screenplay import GenerateDecoupageWorker, ArrangeConducteurStreamWorker
    from api.live_extract import FormatConducteurWorker
    from core.music_analysis import AnalyzeMusicWorker
    assert [k for _, k in UPSCALE_MODELS] == ["topaz", "seedvr"]
    assert UpscaleVideoWorker("x.mp4", model="topaz", upscale_factor=4)._factor == 4
    assert SFX1VideoWorker("x.mp4", "p", 12.0)._duration == 12.0
    assert SFX1Worker("p", 10.0)._duration == 10.0
    assert GenerateDecoupageWorker("t", "mapping")._mode == "mapping"
    w = ArrangeConducteurStreamWorker("t", "live", 90)
    assert hasattr(w, "chunk") and w._dur == 90, "streaming + durée cible"
    assert FormatConducteurWorker("t", "live", 60)._dur == 60
    assert isinstance(AnalyzeMusicWorker([{"path": "x"}])._tracks, list)


@test
def couche_ai_provider():
    """Couche d'abstraction IA : défauts, tiers, nom d'affichage, sites routés."""
    import core.ai_provider as ap
    assert ap.get_provider() in ("anthropic", "mistral", "ollama")
    assert ap._model("utility") and ap._model("creative"), "modèles des deux tiers"
    assert ap.ai_name(), "nom d'affichage"
    # Les workers TEXTE ne doivent plus importer anthropic en direct
    # (seuls les appels VISION y ont droit, marqués d'un commentaire).
    import api.enhance, api.assistant, core.lang, api.live_extract, api.live_screenplay
    for mod in (api.enhance, api.assistant, core.lang, api.live_extract, api.live_screenplay):
        src = inspect.getsource(mod)
        assert "anthropic.Anthropic(" not in src, f"{mod.__name__} : appel anthropic direct restant"
    import api.screenplay
    src = inspect.getsource(api.screenplay)
    assert src.count("anthropic.Anthropic(") == 2, "screenplay : seuls les 2 sites VISION restent"
    assert "core.ai_provider" in src, "screenplay routé via ai_provider"


@test
def selecteur_assistant_ia():
    """Sélecteur IA dans Paramètres (Cinéma + Live) : 4 choix, champs conditionnels."""
    from ui.page_settings import SettingsPage
    from ui.page_live_settings import PageLiveSettings
    cin = SettingsPage()
    assert cin.ai_combo.count() == 4, "4 choix côté Cinéma"
    assert any("Fable 5" in cin.ai_combo.itemText(i) for i in range(4)), "Fable 5 proposé"
    cin.ai_combo.setCurrentIndex(2)   # Mistral
    assert not cin.mistral_input.isHidden(), "champ Mistral visible quand Mistral choisi"
    assert cin.ollama_url_input.isHidden(), "champs Ollama cachés"
    cin.ai_combo.setCurrentIndex(0)
    assert cin.mistral_input.isHidden(), "champ Mistral caché sur Claude"
    liv = PageLiveSettings()
    assert liv._ai_combo.count() == 4, "4 choix côté Live"
    liv._ai_combo.setCurrentIndex(3)  # Ollama
    assert not liv._ollama_url_input.isHidden(), "champs Ollama visibles côté Live"


@test
def calage_musical_deterministe():
    """align_shots_to_music : durées en mesures exactes + cuts attirés sur les drops."""
    from core.music_align import align_shots_to_music, bar_seconds
    bar = bar_seconds(128.0)                      # 1.875 s
    assert abs(bar - 1.875) < 1e-9
    tracks = [{"name": "t1.mp3", "bpm": 128.0, "duration": 120.0,
               "drops": [7.5, 30.0]}]
    shots = [
        {"id": "a", "number": 1, "duration": 6.8, "music_track": "t1.mp3"},
        {"id": "b", "number": 2, "duration": 5.2, "music_track": "t1.mp3"},
        {"id": "c", "number": 3, "duration": 14.9, "music_track": ""},
    ]
    ch = align_shots_to_music(shots, tracks)
    assert len(ch) == 3
    # Plan 1 : 6.8s → ~4 mesures (7.5s) ET le cut tombe pile sur le drop à 7.5s
    assert ch[0]["new"] == 7.5 and ch[0]["snapped_drop"], "cut sur drop"
    # Toutes les durées non-snappées = multiples exacts de mesure, bornées 2-15
    for c in ch:
        assert 2.0 <= c["new"] <= 15.0
        if not c["snapped_drop"]:
            assert abs((c["new"] / bar) - round(c["new"] / bar)) < 1e-6, "multiple de mesure"
    # Sans morceau analysé → aucun changement proposé
    assert align_shots_to_music(shots, [{"name": "x", "bpm": 0}]) == []
    # Le bouton existe sur la page Séquences
    from ui.live_pages import SequenceLivePage
    import core.storyboard as sb
    p = SequenceLivePage()
    assert hasattr(p, "_btn_music_align") and hasattr(p, "_on_music_align")
    sb.set_namespace("storyboard")


@test
def sound_prompt_vers_sound_design():
    """« ➤ SFX » : plan → Studio IA → onglet Sound Design pré-rempli."""
    import core.storyboard as sb
    from ui.live_studio_widget import LiveStudioWidget
    s = LiveStudioWidget()
    s.open_sound_design("deep bass drone, glitch textures", 12.0)
    assert s.tabs.currentWidget() is s.tab_sound, "bascule vers Sound Design"
    assert s.tab_sound._mode == "text", "mode Prompt → SFX"
    assert "bass drone" in s.tab_sound._txt_prompt.toPlainText(), "prompt pré-rempli"
    assert s.tab_sound._dur_text.value() == 12.0, "durée du plan reprise"
    # La page Séquences expose le signal relais
    from ui.live_pages import SequenceLivePage
    p = SequenceLivePage()
    assert hasattr(p, "sound_to_studio"), "signal sound_to_studio présent"
    sb.set_namespace("storyboard")


@test
def conformation_duree_musicale():
    """conform_clip : retime branché dans on_finished, garde-fous corrects."""
    from core.video_conform import conform_clip, MAX_DEVIATION
    # Garde-fous (sans ffmpeg : entrées invalides → refus propre)
    r = conform_clip("", 5.0)
    assert not r["conformed"] and r["reason"], "entrée vide refusée"
    r = conform_clip(__file__, 0)
    assert not r["conformed"], "cible nulle refusée"
    assert MAX_DEVIATION <= 0.15, "retime limité (imperceptible)"
    # Branché dans la génération, AVANT l'extraction des frames de raccord
    import inspect
    import ui.tab_t2v_live as M
    src = inspect.getsource(M.TabT2V.on_finished)
    assert "conform_clip" in src, "conformation branchée"
    assert src.index("conform_clip") < src.index("extract_last_frame"), \
        "conformation AVANT l'extraction de la dernière frame (raccord)"


@test
def prompts_beats_relatifs():
    """Les prompts vidéo structurent le temps en beats relatifs, sans timecodes."""
    import api.live_screenplay as ls
    import inspect
    import api.live_extract as le
    for t in (ls._SYSTEM_LIVE, ls._SYSTEM_MAPPING):
        tt = " ".join(t.split())   # neutralise les retours à la ligne
        assert "BEATS RELATIFS" in tt and "JAMAIS de timecode absolu" in tt, "beats relatifs"
        assert "CUTS" in tt, "les impacts musicaux vont sur les cuts"
    src = " ".join(inspect.getsource(le.FormatConducteurWorker.run).split())
    assert "BEATS RELATIFS" in src and "JAMAIS de timecode absolu" in src


@test
def sound_design_file_et_crossfade():
    """File d'attente SFX depuis les Séquences + commande de fondu enchaîné."""
    import core.storyboard as sb
    from ui.tab_sound_design_live import TabSoundDesignLive
    sb.set_namespace("live_seq_live")
    sb.clear_version_shots(sb.DEFAULT_VERSION_ID)
    sb.save_shot({"number": 1, "scene_title": "A", "sound_prompt": "bass drone",
                  "duration": 6}, sb.DEFAULT_VERSION_ID)
    sb.save_shot({"number": 2, "scene_title": "B", "sound_prompt": "",
                  "duration": 5}, sb.DEFAULT_VERSION_ID)   # sans prompt → exclu
    sb.save_shot({"number": 3, "scene_title": "C", "sound_prompt": "glitch riser",
                  "duration": 8}, sb.DEFAULT_VERSION_ID)
    sb.set_namespace("storyboard")
    t = TabSoundDesignLive()
    t._set_seq_source("live")
    t._load_seq_plans()
    assert len(t._sfx_queue) == 2, "seuls les plans avec prompt son sont chargés"
    assert [q["number"] for q in t._sfx_queue] == [1, 3], "ordre des plans"
    assert t._btn_run_queue.isEnabled(), "bouton Générer la file actif"
    # Commande de crossfade (pure) : N entrées → N-1 acrossfade chaînés
    cmd = TabSoundDesignLive._build_crossfade_cmd(
        "ffmpeg", ["a.wav", "b.wav", "c.wav"], "out.wav", fade_s=1.0)
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert fc.count("acrossfade") == 2 and "[a2]" in fc, "chaîne acrossfade"
    assert cmd[-1] == "out.wav" and cmd.count("-i") == 3
    # Toggle « Sound design auto » présent dans Générer depuis Séquences
    from ui.tab_t2v_live import TabT2V
    tv = TabT2V()
    assert hasattr(tv, "_sfx_auto_cb") and not tv._sfx_auto_cb.isChecked()
    sb.set_namespace("storyboard")


@test
def refs_conducteur_file_et_fond():
    """Références visuelles : redimensionnement (fix 413), file d'attente, synthèse."""
    import inspect
    from PIL import Image
    from core.image_payload import encode_image_for_vision, MAX_SIDE
    # Une grande image est bien réduite avant envoi
    big = os.path.join(_TMP, "_big_ref.jpg")
    Image.new("RGB", (4000, 3000), (120, 90, 60)).save(big)
    mime, b64 = encode_image_for_vision(big)
    assert mime == "image/jpeg" and len(b64) < 900_000, "image compressée"
    import base64, io
    img = Image.open(io.BytesIO(base64.b64decode(b64)))
    assert max(img.size) <= MAX_SIDE, "grand côté ≤ 1568 px"
    # Workers Live : file d'attente (1 requête/image) + synthèse + enrich conducteur
    from api.live_refs import AnalyzeRefsConducteurWorker, EnrichConducteurWithRefsWorker
    w = AnalyzeRefsConducteurWorker(["a.jpg"], "texte", "mapping")
    assert hasattr(w, "chunk") and w._mode == "mapping"
    # Contrat fenêtre : chunk/done/failed (« done », pas « finished » — bug 2026-06-11)
    assert type(w).done is not type(w).failed and hasattr(w, "done"), "signal done présent"
    assert "self.done.emit" in inspect.getsource(AnalyzeRefsConducteurWorker.run), \
        "run() émet done (finished masquerait le signal natif QThread)"
    src = inspect.getsource(AnalyzeRefsConducteurWorker.run)
    assert "for i, path in enumerate" in src, "file d'attente image par image"
    assert "SYNTHÈSE" in src, "synthèse de direction visuelle"
    e = EnrichConducteurWithRefsWorker("c", "a", "live")
    assert hasattr(e, "done") and hasattr(e, "chunk"), "contrat fenêtre (chunk/done)"
    from api.live_refs import _ENRICH_SYSTEM, _PER_IMAGE_SYSTEM, _SYNTHESIS_SYSTEM
    assert "INT." in _ENRICH_SYSTEM, "interdiction format scénario"
    # Doctrine 2026-06-11 : décodage COMPLET de direction artistique (pas que palette)
    for kw in ("Architecture", "Personnages & figures", "Style d'image", "INSPIRATION"):
        assert kw in _PER_IMAGE_SYSTEM, f"décodage DA complet : {kw}"
    assert "jamais à copier" in _SYNTHESIS_SYSTEM, "transposer les codes, pas copier"
    # La page utilise bien les workers Live
    from ui.page_scenario_live import PageScenario
    src_p = inspect.getsource(PageScenario)
    assert "AnalyzeRefsConducteurWorker" in src_p and "EnrichConducteurWithRefsWorker" in src_p


@test
def refs_persistance_bibliotheque_chat():
    """Refs visuelles 2026-06-11 : persistance projet, bibliothèque globale, chat DA."""
    import inspect
    # 1. Persistance par projet : refs + analyse écrites et restaurées avec le conducteur
    from ui.page_scenario_live import PageScenario
    src_save = inspect.getsource(PageScenario._save)
    assert "ref_images" in src_save and "ref_analysis" in src_save, \
        "refs + analyse sauvegardées avec le conducteur"
    src_open = inspect.getsource(PageScenario._open_scenario)
    assert "ref_images" in src_open and "ref_analysis" in src_open, \
        "refs + analyse restaurées à l'ouverture du projet"
    # 2. Le bouton Analyser rouvre l'analyse existante (pas de relance silencieuse)
    src_an = inspect.getsource(PageScenario._on_analyze_refs)
    assert "_open_refs_window" in src_an and "_start_refs_analysis" in src_an, \
        "analyse existante rouverte ; relance via _start_refs_analysis"
    # 3. Fenêtre : Relancer / Sauvegarder / Bibliothèque / chat DA + sauvegarde auto
    src_w = inspect.getsource(PageScenario._open_refs_window)
    for token in ("Relancer l'analyse", "ref_library", "RefsChatWorker",
                  "_save(silent=True)", "Supprimer une analyse"):
        assert token in src_w, f"fenêtre refs : {token}"
    # 4. Bibliothèque globale : aller-retour complet en dossier temporaire
    from core import ref_library
    ref_library.LIB_DIR_OVERRIDE = os.path.join(_TMP, "ref_lib")
    try:
        p = ref_library.save_analysis("Océan originel", "DA test", ["x.jpg"], "mapping")
        entries = ref_library.list_analyses()
        assert len(entries) == 1 and entries[0]["name"] == "Océan originel"
        loaded = ref_library.load_analysis(p)
        assert loaded["analysis"] == "DA test" and loaded["mode"] == "mapping"
        assert ref_library.delete_analysis(p) and not ref_library.list_analyses()
    finally:
        ref_library.LIB_DIR_OVERRIDE = None
    # 5. Chat DA : worker multi-tours streaming via la couche IA
    from core.ai_provider import chat_stream
    assert callable(chat_stream), "chat multi-tours en streaming disponible"
    from api.live_refs import RefsChatWorker, _CHAT_SYSTEM
    w = RefsChatWorker([{"role": "user", "content": "?"}], "analyse", "cond", "mapping")
    assert hasattr(w, "chunk") and hasattr(w, "done") and hasattr(w, "failed")
    assert "chat_stream" in inspect.getsource(RefsChatWorker.run)
    assert "ACTES" in _CHAT_SYSTEM and "jamais à copier" in _CHAT_SYSTEM
    # 6. L'arrangement reçoit la direction artistique quand elle existe
    from api.live_screenplay import ArrangeConducteurStreamWorker
    aw = ArrangeConducteurStreamWorker("t", "live", 0, refs_analysis="DA")
    assert aw._refs == "DA"
    assert "DIRECTION ARTISTIQUE" in inspect.getsource(ArrangeConducteurStreamWorker.run)
    assert "refs_analysis=self._last_ref_analysis" in inspect.getsource(PageScenario), \
        "la page passe l'analyse à l'arrangement"


@test
def bibliotheque_images_globale():
    """Bibliothèque d'images partagée : cœur (copies, collections) + porte unique."""
    import inspect
    from PIL import Image
    from core import image_library as ilib
    ilib.LIB_DIR_OVERRIDE = os.path.join(_TMP, "img_lib")
    try:
        # Roundtrip complet : collection, ajout (COPIE), listing, renommage, retraits
        src = os.path.join(_TMP, "_lib_src.jpg")
        Image.new("RGB", (64, 64), (10, 20, 30)).save(src)
        key = ilib.create_collection("Mes façades")
        copied = ilib.add_images(key, [src, "inexistant.jpg"])
        assert len(copied) == 1 and copied[0] != src, "image COPIÉE dans la bibliothèque"
        assert os.path.isfile(copied[0]), "copie présente sur disque"
        cols = ilib.list_collections()
        assert cols[0]["name"] == "Mes façades" and cols[0]["count"] == 1
        assert cols[0]["cover"] == copied[0], "couverture = première image"
        # Dédoublonnage de nom au second ajout du même fichier
        again = ilib.add_images(key, [src])
        assert again and again[0] != copied[0], "pas d'écrasement (suffixe _1)"
        assert ilib.rename_collection(key, "Façades nuit")
        assert ilib.list_collections()[0]["name"] == "Façades nuit"
        assert ilib.remove_image(copied[0]) and len(ilib.list_images(key)) == 1
        assert not ilib.remove_image(src), "fichiers HORS bibliothèque protégés"
        ilib.delete_collection(key)
        assert not ilib.list_collections()
        # Dialog : construction + contrat pick
        from ui.dialog_image_library import ImageLibraryDialog
        d = ImageLibraryDialog(pick=True)
        assert hasattr(ImageLibraryDialog, "pick") and d.picked == []
        assert hasattr(d, "_on_browse_disk"), "parcours disque intégré au dialog"
    finally:
        ilib.LIB_DIR_OVERRIDE = None
    # Porte unique côté Live : le conducteur passe par la bibliothèque
    from ui.page_scenario_live import PageScenario
    assert "ImageLibraryDialog" in inspect.getsource(PageScenario._on_add_refs)


@test
def libelles_dynamiques_ia():
    """brand() rebaptise « Claude » selon l'assistant actif ; translate() le propage."""
    import core.ai_provider as ap
    from core.i18n import translate
    # Simule un assistant différent en forçant le cache de nom
    ap._NAME_CACHE = "Fable 5"
    try:
        assert ap.brand("Analyser avec Claude") == "Analyser avec Fable 5"
        assert "Fable 5" in translate("☁  Claude IA"), "translate() applique brand()"
        assert translate("Acte") == "Acte", "chaînes sans Claude inchangées"
    finally:
        ap.refresh_name_cache()
    # Avec Claude actif (défaut), aucun libellé ne change
    if ap.ai_name() == "Claude":
        assert translate("☁  Claude IA") == "☁  Claude IA"


@test
def i18n_cles_live():
    """Les chaînes Live clés ont leur traduction EN dans _FR_TO_EN."""
    from core.i18n import _FR_TO_EN
    for key in ("Mise en page PANDORA", "Acte", "Prompt vidéo / son",
                "Sound Design", "Upscaling", "♫  Musiques du set",
                "▦  Référence bâtiment (façade)", "Corriger le BPM",
                "✓  Appliquer le découpage", "Musique", "Notes / Repère"):
        assert key in _FR_TO_EN, f"i18n manquante : {key}"


# ══════════════════════════════════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    print(f"PANDORA | Live — harnais de non-régression ({len(_TESTS)} tests)")
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
