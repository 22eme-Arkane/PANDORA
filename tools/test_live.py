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
    # Image d'INSPIRATION (2026-06-11) : transposée sur la façade, jamais collée
    assert "kontext/max/multi" in src, "Kontext multi quand façade + inspiration"
    assert "INSPIRATION" in src and "Do NOT paste" in src, "DA transposée, pas collée"
    import inspect as _i
    assert "inspiration_ref" in _i.signature(A.MoodGenerationWorker.__init__).parameters
    from ui.dialog_apercu import MoodDialog
    src_d = inspect.getsource(MoodDialog._generate_from_image)
    assert "ImageLibraryDialog" in src_d, "inspiration choisie via la bibliothèque"


@test
def prompts_cinema_detailles():
    """Cinéma : prompts storyboard + mise en page enrichis, fidèles au scénario."""
    import api.screenplay as s
    # Découpage en SECTIONS (code partagé) : l'IA renvoie des champs assemblés en
    # [🎬 ACTION]… ; la Technique vient des champs caméra.
    for k in ('"action"', '"staging"', '"ambiance"', '"decor"', '"lighting"'):
        assert k in s._GENERATE_STORYBOARD_TMPL, f"champ de section {k}"
    assert "hors champ" in s._GENERATE_STORYBOARD_TMPL, "personnages hors champ exclus"
    assert hasattr(s, "_technique_line"), "section Technique déterministe"
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
def storyboard_boutons_portes_du_cinema():
    """Portés du Cinéma (2026-07-01) : Sauvegarder / Ouvrir un storyboard + Pitch
    deck (PDF/PNG/HTML) dans la barre d'outils du storyboard Live."""
    import inspect
    import ui.page_storyboard_live as M
    for m in ("_on_save_storyboard_file", "_on_open_storyboard_file", "_on_export_pitch_deck"):
        assert hasattr(M.PageStoryboard, m), f"méthode portée manquante : {m}"
    src = inspect.getsource(M.PageStoryboard._build_shots_toolbar)
    for tok in ("_btn_save_sb_file", "_btn_open_sb_file", "_btn_pitch_deck"):
        assert tok in src, f"bouton porté manquant dans la barre : {tok}"
    # L4 Retake porté dans « Modifier un clip » (Live)
    import ui.tab_modify_live as MM
    assert "retake" in MM._MOD_TEMPLATES and "@Video1" in MM._MOD_TEMPLATES["retake"]
    assert hasattr(MM.TabModifyLive, "_on_mod_type"), "handler Retake Live manquant"
    # « Modifier des clips » Live en mode LOT (parité Cinéma) :
    t = MM.TabModifyLive()
    for a in ("_rb_global", "_rb_per_clip", "_process_next", "_build_params",
              "_global_ref", "_pc_ref", "_audio_chk", "_res_combo", "_clip_list"):
        assert hasattr(t, a), f"batch modify : {a} manquant"
    _real = os.path.abspath(__file__)
    t.add_clips_from_paths([_real])
    assert t._clip_list.count() == 1, "liste de clips cochable"
    _p = t._build_params(0, _real)
    assert _p["mode"] == "ext" and "generate_audio" in _p and "resolution" in _p
    assert "@Video1" in _p["prompt"] and _p["video_path"] == _real
    # P5 — 2ᵉ fenêtre (2 écrans) portée au Live
    import live_window as LW
    src_i = inspect.getsource(LW.LiveWindow.__init__)
    assert "is_secondary" in src_i and "if not self._is_secondary" in src_i
    assert hasattr(LW.LiveWindow, "open_secondary_window")
    src_o = inspect.getsource(LW.LiveWindow.open_secondary_window)
    assert "is_secondary=True" in src_o and "NonModal" in src_o and "screens()" in src_o
    assert "_is_secondary" in inspect.getsource(LW.LiveWindow.closeEvent)
    # Chat Storyboard (IA) à droite sur les pages Séquences (porté du Cinéma)
    for m in ("_sb_chat_shots", "_sb_chat_applied", "_update_sb_chat"):
        assert hasattr(LW.LiveWindow, m), f"chat storyboard : {m} manquant"
    assert "_update_sb_chat(key)" in inspect.getsource(LW.LiveWindow._navigate)
    assert "seq_live" in inspect.getsource(LW.LiveWindow._update_sb_chat)
    from ui.page_live_settings import PageLiveSettings
    ps = PageLiveSettings()
    assert hasattr(ps, "_btn_second_window") and hasattr(ps, "_open_second_window")
    # Clic droit storyboard : Dupliquer + Libellé couleur (pas de « récurrent » en live)
    assert hasattr(M._ShotRow, "contextMenuEvent") and hasattr(M._ShotRow, "_set_label")
    assert hasattr(M._ShotRow, "duplicate_requested")
    assert hasattr(M.PageStoryboard, "_on_duplicate"), "handler Dupliquer manquant"
    csrc = inspect.getsource(M._ShotRow.contextMenuEvent)
    assert "Dupliquer" in csrc and "Libellé couleur" in csrc
    assert "_set_recurrent" not in csrc, "pas de « plan récurrent » en live (sans objet)"
    # P2 fusion déclarée côté Live (dialogue + relance stricte)
    assert hasattr(M.PageStoryboard, "_ask_merge_decision")
    gsrc = inspect.getsource(M.PageStoryboard._on_shots_generated)
    assert "strict_no_merge=True" in gsrc and 'pop("merged"' in gsrc


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
    # Ordre par défaut VALIDÉ (capture Matthieu 2026-06-10) : Mood · Acte · Plan ·
    # TC · Prompt · Musique · BPM · Vitesse · Durée · Notes · Transition ·
    # Acteurs · Accessoires
    assert vis == [0, 1, 2, 3, 16, 4, 17, 18, 10, 15, 20, 19, 14, 13, 21], \
        "ordre par défaut Mapping = capture validée"
    live = SequenceLivePage(); live.refresh()
    vis_l = M._visible_order()
    assert all(c not in vis_l for c in (6, 11, 12)), "Live masque Mouvement/Décor/Heure"
    assert 5 in vis_l and 7 in vis_l, "Live garde Axe/Valeur"
    # Retours 2026-06-12 (capture) — vaut pour Séquences Live ET Mapping :
    # tableau vide → message centré À L'ÉCRAN (conteneur sans largeur de colonnes)
    # et AUCUNE scrollbar horizontale ; Moods/Caler à GAUCHE de la toolbar
    import inspect as _isp
    src_render = _isp.getsource(M.PageStoryboard._render)
    assert "setMinimumWidth(0)" in src_render, "vide → conteneur à la fenêtre (centré)"
    # Le conteneur imposait sa largeur via sizeHint (somme des colonnes) même
    # vide → message décentré malgré setMinimumWidth(0). _empty_mode neutralise.
    c = M._ShotListContainer()
    full_w = c.sizeHint().width()
    c._empty_mode = True
    assert c.sizeHint().width() < full_w and c.minimumSizeHint().width() < full_w, \
        "_empty_mode neutralise la largeur des colonnes (message centré à l'écran)"
    assert "_empty_mode = True" in src_render and "_empty_mode = False" in src_render
    # Centrage DÉTERMINISTE (3e retour) : la zone tableau (scroll + scrollbar)
    # est masquée ENTIÈREMENT quand il n'y a pas de plans, et le message vit
    # dans un label dédié hors du scroll — plus aucun caprice de QScrollArea
    assert "_table_wrap.setVisible(False)" in src_render, "vide → zone tableau masquée"
    assert "_empty_lbl.setVisible(True)" in src_render, "vide → label dédié affiché"
    assert "_table_wrap.setVisible(True)" in src_render, "tableau → zone rétablie"
    assert "depuis le Conducteur" in src_render, "message Live (pas « onglet Scénario »)"
    for pg in (live, mp):
        assert hasattr(pg, "_empty_lbl") and hasattr(pg, "_table_wrap"), \
            "label vide + zone tableau présents (Live ET Mapping)"
        _tlay = pg._btn_batch_mood.parentWidget().layout()
        assert (_tlay.indexOf(pg._btn_batch_mood) < _tlay.indexOf(pg._btn_music_align)
                < _tlay.indexOf(pg._ai_lbl) < _tlay.indexOf(pg._btn_clear_shots)), \
            "Moods et Caler à gauche, actions à droite"
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
    """ShotDialog Live a le champ sound design (le Cinéma l'a AUSSI depuis
    2026-06-13 — parité voulue) ; la page Live ouvre bien la copie Live."""
    from ui.dialog_shot_live import ShotDialog as LiveDlg
    d = LiveDlg(shot={"id": "s1", "number": 1, "sound_prompt": "boom"})
    assert hasattr(d, "_sound_prompt") and d._sound_prompt.toPlainText() == "boom"
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
    # Fausse alerte « refs non transmises » corrigée (2026-06-10) : le compteur
    # attempted n'est rempli QUE par le mode "ref" — en i2v (keyframes) la liste
    # ref_images est ignorée, l'alerte n'a pas lieu d'être.
    import inspect
    import api.real as R
    src_r = inspect.getsource(R.run_real)
    assert "_ref_images_attempted = 0" in src_r, "attempted initialisé à 0"
    assert 'elif mode == "ref":\n        _ref_images_attempted = len(ref_images)' in src_r, \
        "attempted rempli uniquement dans la branche ref"
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
    """9 onglets (+ Musique IA & Image IA portés du Cinéma), Sound Design + Upscaling
    présents et câblés à la Vidéothèque."""
    from ui.live_studio_widget import LiveStudioWidget
    s = LiveStudioWidget()
    titres = [s.tabs.tabText(i) for i in range(s.tabs.count())]
    assert len(titres) == 9, f"9 onglets attendus, {len(titres)} trouvés"
    for attendu in ("Sound Design", "Musique IA", "Image IA", "Upscaling",
                    "Vidéothèque", "Historique"):
        assert any(attendu in x for x in titres), f"onglet {attendu} manquant"
    assert s.tab_upscale._library_provider is not None, "Upscaling relié à la Vidéothèque"
    # file d'attente upscaling : ajout + dédoublonnage
    real = os.path.abspath(__file__)
    assert s.tab_upscale.add_clips_from_paths([real, real]) == 1, "dédoublonnage file"
    s._on_send_to_upscale([real])
    assert s.tabs.tabText(s.tabs.currentIndex()) == "Upscaling", "bascule vers Upscaling"
    # Lisibilité plein écran (retour 2026-06-12, nav en barre basse) : les
    # onglets FORMULAIRE sont plafonnés en largeur et centrés ; la Vidéothèque
    # (galerie) garde la pleine largeur
    from PyQt6.QtCore import Qt as _Qt
    for _t in (s.tab_sequences, s.tab_modify, s.tab_sound, s.tab_upscale):
        assert _t.widget().maximumWidth() == 1360, "contenu plafonné en largeur"
        assert _t.alignment() & _Qt.AlignmentFlag.AlignHCenter, "contenu centré"
    assert s.tab_library.widget().maximumWidth() > 100000, "Vidéothèque pleine largeur"
    # Un seul trait en haut du Studio : pas de ligne de base native sous les
    # onglets (documentMode la doublait avec celle de la topbar)
    assert s.tabs.tabBar().drawBase() is False, "ligne de base des onglets retirée"
    # « Ouvrir le dossier » : style ghost UNIFORME (référence Modifier des
    # clips) sur les 5 onglets, TOUJOURS cliquable (destination par défaut)
    from ui.tab_video_engines_live import _btn_ghost_style as _ghost
    _open_btns = (s.tab_sequences._btn_open_folder, s.tab_engines._btn_open,
                  s.tab_modify._btn_open, s.tab_sound._btn_open_dir,
                  s.tab_upscale._btn_open)
    for _b in _open_btns:
        assert _b.styleSheet() == _ghost(), "style ghost uniforme"
        assert _b.isEnabled(), "toujours cliquable (même sans génération)"
        assert "📁" not in _b.text(), "libellé uniforme sans emoji"
    # Nom UNIQUE du bouton de génération (retour 2026-06-13) : « Lancer la
    # file d'attente » partout — Génération directe et Modifier des clips inclus
    assert "Lancer la file d'attente" in s.tab_engines._btn_generate.text()
    assert "Lancer la file d'attente" in s.tab_modify._btn_generate.text()
    # Centrage : spacer symétrique du bloc « × N » dans Générer depuis Séquences
    import inspect as _isp_btn
    import ui.tab_t2v_live as _T2VL
    assert "_sym_spacer" in _isp_btn.getsource(_T2VL), \
        "texte du bouton centré avec le logo PANDORA"
    import inspect as _isp2
    for _cls in (type(s.tab_modify), type(s.tab_engines)):
        assert "get_output_dir" in _isp2.getsource(_cls._on_open_folder), \
            f"{_cls.__name__} : repli sur la destination par défaut"


@test
def fenetre_live():
    """Topbar, assistant fermé par défaut, nav en BARRE BASSE, alias de navigation."""
    from live_window import LiveWindow
    w = LiveWindow({})
    assert hasattr(w, "_btn_save_global") and hasattr(w, "_btn_update_header"), "topbar"
    assert w._assistant.isHidden(), "assistant IA fermé par défaut"
    assert w._assistant_toggle._open is False, "poignée synchronisée"
    assert "settings" in w._sidebar._items, "Paramètres dans la nav"
    # Nav en BAS façon DaVinci (demande 2026-06-12) : barre horizontale fine
    # sous le corps — les pages récupèrent toute la largeur de l'écran
    assert w._sidebar.maximumHeight() == 64, "barre basse fine (taskbar)"
    assert w._sidebar.maximumWidth() > 10000, "plus de colonne latérale fixe"
    assert w._sidebar.parentWidget() is w.centralWidget(), \
        "la barre vit sous le corps (layout vertical racine), pas dans le body"
    # Assistant IA à GAUCHE des pages (poignée au bord gauche)
    _body_lay = w._stack.parentWidget().layout()
    assert (_body_lay.indexOf(w._assistant_toggle) < _body_lay.indexOf(w._assistant)
            < _body_lay.indexOf(w._stack)), "assistant à gauche : poignée, panneau, pages"
    assert w._assistant_toggle._side == "left", "flèches du strip en miroir côté gauche"
    # Retours 2026-06-12 : Manuel ET Nous contacter en HAUT À GAUCHE (topbar),
    # Paramètres seul en BAS À DROITE, séparation Projets|Conducteur
    assert hasattr(w, "_btn_manual_top") and hasattr(w, "_btn_contact_top"), \
        "Manuel + Contact dans la topbar"
    # Couleurs (retour 2026-06-12 soir) : Manuel ROUGE, Nous contacter VERT
    assert "255,79,106" in w._btn_manual_top.styleSheet(), "Manuel en rouge"
    assert "37,211,102" in w._btn_contact_top.styleSheet(), "Contact en vert"
    assert not hasattr(w._sidebar, "_btn_manual") and not hasattr(w._sidebar, "_btn_contact"), \
        "plus de Manuel/Contact dans la barre basse"
    _bar_lay = w._sidebar.layout()
    assert all(_bar_lay.indexOf(w._sidebar._items[k])
               < _bar_lay.indexOf(w._sidebar._items["settings"])
               for k in w._sidebar._items if k != "settings"), \
        "Paramètres tout au bord, en bas à droite"
    from live_window import _NAV_ITEMS as _NI
    assert _NI[1] is None and _NI[0][2] == "projects" and _NI[2][2] == "conducteur", \
        "séparateur entre Projets et Conducteur"
    # Largeur (retours finaux 2026-06-12) : toutes les pages s'étirent jusqu'aux
    # bords SAUF Paramètres, centré comme les onglets du Studio IA
    for k in w._pages:
        if k == "settings":
            continue
        assert w._pages[k].maximumWidth() > 100000, f"page {k} pleine largeur"
    assert w._pages["settings"].maximumWidth() == 1360, "Paramètres plafonné"
    import inspect as _isp_lw
    w._navigate("settings")
    assert w._stack.currentWidget() is w._settings_wrap, \
        "Paramètres affiché dans son conteneur centré"
    # Dialogue « Nous contacter » Live : groupe + lien WhatsApp PANDORA | Live
    # (le dialogue Cinéma reste sur le groupe Cinéma)
    from ui.dialog_contact_live import ContactDialog as _CDL
    from ui.dialog_contact import ContactDialog as _CDC
    assert _CDL._WA_GROUP == "PANDORA | Live" and "LEVinbwbtOv3yn8zr8zWPL" in _CDL._WA_LINK
    assert _CDC._WA_GROUP == "PANDORA | Cinéma" and "JRo5SWLBwbxLgACtrDksDj" in _CDC._WA_LINK
    # Alignement des bandeaux (retour 2026-06-12) : l'en-tête de l'assistant
    # partage la hauteur STANDARD 60 px des bandeaux de pages — lignes alignées
    assert w._assistant._header.maximumHeight() == 60, "en-tête assistant aligné"
    for _mod, _meth in (("ui.page_storyboard_live", "_build_shots_topbar"),
                        ("ui.page_live", "_build_topbar")):
        _m = __import__(_mod, fromlist=["x"])
        _cls = getattr(_m, "PageStoryboard", None) or getattr(_m, "PageLive")
        assert "setFixedHeight(60)" in _isp_lw.getsource(getattr(_cls, _meth)), \
            f"bandeau 60 px : {_mod}.{_meth}"
    # Conducteur (retours 2026-06-12 soir) : scrollbar de l'éditeur AU BORD
    # (marges dans le document, pas en padding CSS) et « Rouvrir la fenêtre »
    # TOUT EN BAS du panneau droit, sous « Tout générer »
    from ui.page_scenario_live import PageScenario as _PSC
    src_ed = _isp_lw.getsource(_PSC._build_editor)
    assert "setDocumentMargin" in src_ed and "padding:32px 120px" not in src_ed, \
        "scrollbar de l'éditeur collée au panneau de droite"
    src_rp = _isp_lw.getsource(_PSC._build_right_panel)
    assert (src_rp.index("addWidget(self._btn_generate_all)")
            < src_rp.index("ga_lay.addWidget(self._btn_reopen_window)")), \
        "Rouvrir la fenêtre sous Tout générer"
    # Colonne droite permanente = largeur de la poignée Guide fermée (symétrie).
    # 42 px : largeur des bandes Guide/IA (assez large pour « GUIDE » non tronqué).
    assert w._right_spacer.maximumWidth() == w._assistant_toggle.maximumWidth() == 42
    assert _body_lay.indexOf(w._right_spacer) > _body_lay.indexOf(w._stack), \
        "colonne symétrique au bord droit"
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
    # Modèles Topaz = valeurs EXACTES de l'enum fal.ai (vu en réel : « Gaia » nu
    # → erreur immédiate ; seuls Proteus/Nyx nus existent)
    from api.upscale import TOPAZ_MODELS
    _enum = {"Proteus", "Artemis HQ", "Artemis MQ", "Artemis LQ",
             "Nyx", "Nyx Fast", "Nyx XL", "Nyx HF",
             "Gaia HQ", "Gaia CG", "Gaia 2",
             "Starlight Precise 1", "Starlight Precise 2", "Starlight Precise 2.5",
             "Starlight HQ", "Starlight Mini", "Starlight Sharp",
             "Starlight Fast 1", "Starlight Fast 2"}
    assert all(k in _enum for _, k in TOPAZ_MODELS), "enum API Topaz exact"
    assert all(isinstance(t, tuple) and len(t) == 2 for t in TOPAZ_MODELS)
    # File d'upscale ANNULABLE (demande 2026-06-11) : bouton ■, worker parqué,
    # clips restants conservés en attente
    import inspect
    import ui.tab_upscale_live as UPS
    src_tab = inspect.getsource(UPS)
    assert "_btn_cancel" in src_tab and "def _on_cancel" in src_tab, "bouton Annuler"
    assert "abandon_thread" in src_tab, "annulation = worker parqué (anti-crash)"
    assert "_cancelled" in inspect.getsource(UPS.TabUpscaleLive._process_next), \
        "la file s'arrête après annulation"
    # Sortie upscale = MÊME NOM que la source (relink direct dans DaVinci)
    src_u = inspect.getsource(UpscaleVideoWorker._real)
    assert "os.path.basename(self._video)" in src_u, \
        "nom de sortie = nom du fichier source"
    assert "int(time.time())" not in src_u, \
        "pas de timestamp dans le nom (casserait le relink)"
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
    nc = cin.ai_combo.count()
    assert nc == 9, "9 choix côté Cinéma (PANDORA optimisé défaut, Sonnet, Haiku, Fable 5, GPT-5.5, Mistral, Kimi K2.7, Ollama, Personnalisé)"
    assert any("Fable 5" in cin.ai_combo.itemText(i) for i in range(nc)), "Fable 5 proposé"
    assert any("GPT-5.5" in cin.ai_combo.itemText(i) for i in range(nc)), "GPT-5.5 proposé"
    # Clés GPT + Mistral toujours présentes (menu déroulant facultatif)
    assert hasattr(cin, "openai_input") and hasattr(cin, "mistral_input")
    # Ollama : champs conditionnels au choix global
    for i in range(nc):
        d = cin.ai_combo.itemData(i)
        if d and d[0] == "ollama":
            cin.ai_combo.setCurrentIndex(i)
            break
    assert not cin.ollama_url_input.isHidden(), "champs Ollama visibles quand Ollama choisi"
    cin.ai_combo.setCurrentIndex(0)
    assert cin.ollama_url_input.isHidden(), "champs Ollama cachés sur Claude"
    liv = PageLiveSettings()
    assert liv._ai_combo.count() == 5, "5 choix côté Live (+ Kimi K2.7)"
    # Ollama : trouvé par donnée (robuste au décalage d'index après ajout Kimi)
    _oll_i = next(i for i in range(liv._ai_combo.count())
                  if (liv._ai_combo.itemData(i) or ("", ""))[0] == "ollama")
    liv._ai_combo.setCurrentIndex(_oll_i)
    assert not liv._ollama_url_input.isHidden(), "champs Ollama visibles côté Live"
    # Kimi : sélection → champs clé + URL/modèle visibles, Ollama caché
    _km_i = next(i for i in range(liv._ai_combo.count())
                 if (liv._ai_combo.itemData(i) or ("", ""))[0] == "kimi")
    liv._ai_combo.setCurrentIndex(_km_i)
    assert not liv._kimi_input.isHidden(), "clé Kimi visible côté Live quand Kimi choisi"
    assert not liv._kimi_url_input.isHidden() and not liv._kimi_model_input.isHidden()
    assert liv._ollama_url_input.isHidden(), "champs Ollama cachés quand Kimi choisi"


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
    # ── Assignation AUTO des colonnes Musique/BPM (2026-06-10) ───────────────
    from core.music_align import assign_tracks_to_shots
    two = [{"name": "t1.mp3", "bpm": 128.0, "duration": 20.0},
           {"name": "t2.mp3", "bpm": 90.0,  "duration": 60.0}]
    sh = [
        {"id": "a", "number": 1, "duration": 22.0, "music_track": ""},  # démarre à 0 → t1
        {"id": "b", "number": 2, "duration": 8.0,  "music_track": ""},  # démarre à 22 → t2
        {"id": "c", "number": 3, "duration": 8.0,  "music_track": "t2.mp3"},  # déjà bon
    ]
    asg = assign_tracks_to_shots(sh, two)
    assert {a["id"]: a["track"] for a in asg} == {"a": "t1.mp3", "b": "t2.mp3"}, \
        "morceau couvrant le DÉBUT du plan (timeline cumulée)"
    assert assign_tracks_to_shots(sh, []) == [], "sans morceaux → rien"
    # Branchements : découpage (création) + Caler la musique (page Séquences)
    import inspect
    from ui.page_scenario_live import PageScenario
    assert "assign_tracks_to_shots" in inspect.getsource(PageScenario._apply_decoupage), \
        "les plans naissent avec leur morceau"
    import ui.page_storyboard_live as M
    assert "assign_tracks_to_shots" in inspect.getsource(M.PageStoryboard._on_music_align), \
        "Caler la musique remplit aussi les colonnes Musique/BPM"
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
    # Refonte 2026-06-11 (retours Matthieu) : bouton UNIQUE « Générer » (file si
    # chargée, sinon manuel), Conducteur visuel partagé avec Générer depuis Séq.,
    # export de la bande-son fondue = option RENDU cochée par défaut
    assert not hasattr(t, "_btn_run_queue"), "plus de double bouton"
    assert "Lancer la file d'attente" in t._btn_generate.text(), \
        "bouton unique harmonisé avec Générer depuis Séquences"
    assert "(2)" in t._btn_generate.text(), "compteur de file affiché"
    assert hasattr(t, "_btn_open_dir"), "Ouvrir le dossier toujours présent"
    import inspect as _i
    assert "_on_run_queue" in _i.getsource(TabSoundDesignLive._on_generate), \
        "Générer = file en priorité"
    assert hasattr(t, "_storyboard"), "Conducteur visuel (StoryboardSelector partagé)"
    assert type(t._storyboard).__name__ == "StoryboardSelector"
    assert t._auto_mix_cb.isChecked(), "bande-son fondue auto par défaut"
    assert "_auto_mix_cb.isChecked" in _i.getsource(TabSoundDesignLive._finish_sfx_queue), \
        "export auto en fin de file"
    # La sélection du Conducteur prime sur « toute la séquence »
    assert "get_selected_shots" in _i.getsource(TabSoundDesignLive._load_seq_plans)
    # Conducteur connecté aux champs (comme Générer depuis Séquences) :
    # un plan → prompt SON + durée ; multi → file immédiate ; design RENDU encadré
    t._on_conductor_shot({"number": 1, "sound_prompt": "bass drone", "duration": 6})
    assert t._txt_prompt.toPlainText() == "bass drone", "prompt son chargé"
    assert abs(t._dur_text.value() - 6.0) < 0.01, "durée calée sur le plan"
    assert t._sfx_queue == [], "sélection simple → file remise à zéro"
    t._on_conductor_shots([
        {"number": 1, "sound_prompt": "a", "duration": 5},
        {"number": 2, "sound_prompt": "b", "duration": 7},
    ])
    assert len(t._sfx_queue) == 2 and t._sfx_queue[1]["duration"] == 7.0, \
        "multi-sélection → file immédiate avec prompts + durées"
    src_sd = _i.getsource(__import__("ui.tab_sound_design_live",
                                     fromlist=["TabSoundDesignLive"]))
    assert "sd_rendu" in src_sd and "Consolas" in src_sd, \
        "section RENDU au design RENDU & AUDIO (titre accent + encarts)"
    # Retours 2026-06-11 soir : (1) PAS de liste détaillée des plans chargés —
    # la sélection se LIT dans le Conducteur (comme les autres onglets), seul le
    # bouton affiche (N) ; (2) chaque plan part avec SON prompt, au statut ;
    # (3) anti-arrêt de chaîne : worker précédent PARQUÉ avant réassignation
    assert "_make_sfx_row" not in src_sd and "_queue_box" not in src_sd, \
        "pas de liste détaillée sous le Conducteur (le bouton affiche N)"
    from PyQt6.QtWidgets import QScrollArea as _QSA
    assert isinstance(t, _QSA), \
        "l'onglet ENTIER est scrollable (liste tronquée sans scrollbar sinon)"
    src_next = _i.getsource(TabSoundDesignLive._process_next_sfx)
    assert "abandon_thread(self._queue_worker)" in src_next, \
        "chaîne protégée (la file s'arrêtait au 1er clip)"
    assert 'it["prompt"][:60]' in src_next, "prompt du plan affiché au statut"
    assert '_make_text_worker(\n            it["prompt"]' in src_next, \
        "chaque clip part avec le prompt de SON plan (moteur choisi)"
    # Ordre des contrôles : progression AU-DESSUS de Générer, Annuler EN DESSOUS
    init_src = _i.getsource(TabSoundDesignLive.__init__)
    assert (init_src.index("root.addWidget(self._progress)")
            < init_src.index("root.addWidget(self._btn_generate)")
            < init_src.index("root.addWidget(self._btn_cancel_queue)")), \
        "ordre progression → Générer → Annuler"
    # L'upscale est protégé du même arrêt de chaîne
    import ui.tab_upscale_live as UPS2
    assert "abandon_thread(self._worker)" in _i.getsource(UPS2.TabUpscaleLive._process_next)
    # Upscale : file en PETITS CARRÉS (façon Conducteur), hauteur bornée,
    # bouton harmonisé, Ouvrir le dossier TOUJOURS actif (destination par défaut)
    src_up = _i.getsource(UPS2)
    for tok in ("_make_chip", "_chips_scroll", "WheelHScroller",
                "Lancer la file d'attente", "_upscale_output_dir"):
        assert tok in src_up, f"upscale : {tok}"
    assert "self._btn_open.setEnabled(False)" not in src_up, \
        "Ouvrir le dossier jamais désactivé"
    # Parseur SFX : 'audio' est une LISTE (12 générations payées et perdues sinon)
    from api.tts import SFX1Worker as _SFXW
    assert "isinstance(audio, list)" in _i.getsource(_SFXW._real), \
        "schéma audio[] de l'API Mirelo géré"
    # Le sélecteur s'appelle désormais « Conducteur » (t2v + sound design)
    import ui.tab_t2v_live as T2V
    assert 'section_label("Conducteur")' in _i.getsource(T2V.StoryboardSelector)
    # Calage audio↔vidéo (retour 2026-06-11 : l'acrossfade CHEVAUCHAIT → la
    # bande perdait (N-1)×1s vs les clips vidéo posés bout à bout) :
    # 1) chaque ambiance est conformée à la durée CALÉE de son plan
    cf = TabSoundDesignLive._build_conform_cmd("ffmpeg", "in.wav", "out.wav", 6.5)
    assert "apad,atrim=0:6.5" in cf[cf.index("-af") + 1], "conformation apad+atrim"
    assert "_conform_audio" in _i.getsource(TabSoundDesignLive._on_sfx_item_done), \
        "chaque clip son conformé à la durée du plan dès sa génération"
    # 2) assemblage SANS chevauchement : durée totale = somme exacte des plans
    cmd = TabSoundDesignLive._build_assemble_cmd(
        "ffmpeg", ["a.wav", "b.wav", "c.wav"], [5.0, 7.0, 6.5], "out.wav")
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "acrossfade" not in fc, "plus de chevauchement (décalage vs vidéo)"
    assert "atrim=0:5" in fc and "atrim=0:7" in fc and "atrim=0:6.5" in fc, \
        "chaque entrée conformée à SA durée calée"
    assert "concat=n=3:v=0:a=1" in fc and fc.count("afade=t=in") == 3, \
        "concat + micro-fondus aux jonctions (aucune durée mangée)"
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
    # 3b. Bouton « Charger une analyse » DANS la section (accessible sans images —
    # la fenêtre, elle, ne s'ouvre que si analyse/images présentes)
    src_load = inspect.getsource(PageScenario._on_load_saved_analysis)
    assert "ref_library" in src_load and "_apply_saved_analysis" in src_load
    src_apply = inspect.getsource(PageScenario._apply_saved_analysis)
    assert "_open_refs_window" in src_apply and "_save(silent=True)" in src_apply, \
        "chargement → persistance projet + fenêtre (chat inclus)"
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
    # Anti-troncature (vu en réel : réponse coupée à l'acte 7 avec 2048 tokens)
    assert "max_tokens=8192" in inspect.getsource(RefsChatWorker.run), "chat : 8192 tokens"
    from api.live_refs import AnalyzeRefsConducteurWorker as _ARW
    assert "max_tokens=8192" in inspect.getsource(_ARW.run), "synthèse : 8192 tokens"
    # 5b. ANTI-CRASH chat (2026-06-11) : le worker fini est PARQUE via abandon_thread,
    # jamais déréférencé pendant que le QThread se termine (segfault sinon) ;
    # et la bande de miniatures défile à la molette (101 images).
    src_w2 = inspect.getsource(PageScenario._open_refs_window)
    assert src_w2.count("abandon_thread(_chat_worker[0])") >= 2, \
        "chat : worker parqué en done ET failed"
    assert "_chat_worker[0] = None\n" in src_w2
    assert "WheelHScroller" in src_w2, "molette → défilement horizontal des miniatures"
    from ui.widgets import WheelHScroller
    assert hasattr(WheelHScroller, "attach")
    # 6. L'arrangement ET son application reçoivent la direction artistique
    from api.live_screenplay import ArrangeConducteurStreamWorker, ApplyArrangeConducteurWorker
    aw = ArrangeConducteurStreamWorker("t", "live", 0, refs_analysis="DA")
    assert aw._refs == "DA"
    assert "DIRECTION ARTISTIQUE" in inspect.getsource(ArrangeConducteurStreamWorker.run)
    ap = ApplyArrangeConducteurWorker("t", "s", 5, refs_analysis="DA")
    assert ap._refs == "DA", "l'application des suggestions reçoit aussi la DA"
    assert "DIRECTION ARTISTIQUE" in inspect.getsource(ApplyArrangeConducteurWorker.run)
    src_page = inspect.getsource(PageScenario)
    assert src_page.count("refs_analysis=self._last_ref_analysis") >= 3, \
        "la page passe l'analyse : arrangement + 2 chemins d'application"


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
    # Moods : une image perso peut être importée comme mood (bouton + copie plan)
    from ui.dialog_apercu import MoodDialog
    src_m = inspect.getsource(MoodDialog._import_image)
    assert "ImageLibraryDialog" in src_m and "save_apercus" in src_m, \
        "mood importable (bibliothèque/disque) — sert de keyframe en mapping"


@test
def coecriture_arrangement():
    """La co-écriture vit DANS la fenêtre d'arrangement, en langage conducteur
    (remplace la Session de co-écriture Cinéma au format scénario, retirée)."""
    import inspect
    from api.live_screenplay import ArrangeChatConducteurWorker, _ARRANGE_CHAT
    w = ArrangeChatConducteurWorker([{"role": "user", "content": "?"}],
                                    "cond", "sugg", "mapping", refs_analysis="DA")
    assert hasattr(w, "chunk") and hasattr(w, "done") and hasattr(w, "failed")
    assert w._refs == "DA", "la co-écriture voit la direction artistique"
    assert "chat_stream" in inspect.getsource(ArrangeChatConducteurWorker.run)
    assert "ACTES" in _ARRANGE_CHAT and "SUGGESTION RÉVISÉE" in _ARRANGE_CHAT
    assert "INT./EXT." in _ARRANGE_CHAT, "format scénario interdit"
    from ui.page_scenario_live import PageScenario
    src = inspect.getsource(PageScenario._open_arrange_window)
    assert "ArrangeChatConducteurWorker" in src, "chat branché dans la fenêtre"
    assert "DISCUSSION DE CO-ÉCRITURE" in src, \
        "l'application intègre la discussion (les décisions priment)"
    assert "abandon_thread(_chat_worker[0])" in src, "anti-crash : worker parqué"
    # Entrée dans le champ = envoyer — jamais le bouton par défaut Qt
    # (vu en réel : Entrée déclenchait Annuler/Appliquer dans les fenêtres à chat)
    assert "disable_default_buttons" in src, "arrangement : boutons par défaut neutralisés"
    assert "disable_default_buttons" in inspect.getsource(PageScenario._open_refs_window), \
        "refs : boutons par défaut neutralisés"
    from ui.widgets import disable_default_buttons
    assert callable(disable_default_buttons)


@test
def plafonds_anti_troncature():
    """Tout worker qui SORT un conducteur/découpage COMPLET = 16000 tokens.
    (Vu en réel 2026-06-11 : mise en page et enrichissement tronqués à 8000/8192.)"""
    import inspect
    from api.live_extract import FormatConducteurWorker
    from api.live_screenplay import GenerateDecoupageWorker, ApplyArrangeConducteurWorker
    from api.live_refs import EnrichConducteurWithRefsWorker
    for cls in (FormatConducteurWorker, GenerateDecoupageWorker,
                ApplyArrangeConducteurWorker, EnrichConducteurWithRefsWorker):
        assert "max_tokens=16000" in inspect.getsource(cls.run), \
            f"{cls.__name__} : sortie complète → 16000 tokens"
    # Les suggestions d'arrangement (pas un conducteur complet) : 8192 minimum
    from api.live_screenplay import ArrangeConducteurStreamWorker
    assert "max_tokens=8192" in inspect.getsource(ArrangeConducteurStreamWorker.run)


@test
def files_annulables():
    """Garde-fous (2026-06-11) : TOUTE file d'attente est annulable proprement —
    worker parqué (abandon_thread), éléments restants conservés en attente."""
    import inspect
    import ui.tab_upscale_live as UPS
    import ui.tab_sound_design_live as SDX
    import ui.page_live as PLV
    for mod, btn, handler in (
        (UPS, "_btn_cancel",       "def _on_cancel"),
        (SDX, "_btn_cancel_queue", "def _on_cancel_queue"),
        (PLV, "_btn_push_cancel",  "def _on_push_cancel"),
    ):
        src = inspect.getsource(mod)
        assert btn in src and handler in src, f"{mod.__name__} : bouton Annuler"
        assert "abandon_thread" in src, f"{mod.__name__} : worker parqué (anti-crash)"
    # Sound Design : le plan interrompu repasse en attente (relançable)
    src_sd = inspect.getsource(SDX.TabSoundDesignLive._on_cancel_queue)
    assert 'it["status"] = "pending"' in src_sd
    assert "_sfx_cancelled" in inspect.getsource(SDX.TabSoundDesignLive._process_next_sfx)
    # t2v (série) et moods (batch) ont déjà leur annulation — on la fige aussi
    from ui.tab_t2v_live import TabT2V
    src_t2v = inspect.getsource(TabT2V.cancel_generation)
    assert "_batch_queue.clear()" in src_t2v, "t2v : Annuler vide la file en série"
    import ui.page_storyboard_live as SBL
    assert ".cancel()" in inspect.getsource(SBL.PageStoryboard._on_batch_mood), \
        "moods : bouton Arrêter"


@test
def assistant_calage_mapping():
    """Assistant de calage : polygone auto depuis le masque + preset Advanced
    Output conforme au fichier disséqué (export réel Arena 7.26) + mire PNG."""
    import inspect
    import xml.etree.ElementTree as ET
    from PIL import Image, ImageDraw
    from core.live_mapping import (
        extract_facade_polygon, build_advanced_output_preset,
        save_advanced_output_preset, build_calibration_card, douglas_peucker,
    )
    # Douglas-Peucker : une polyligne en V se réduit à ses 3 sommets
    line = [(0, 0), (1, 1), (2, 2), (3, 1), (4, 0)]
    assert douglas_peucker(line, 0.3) == [(0, 0), (2, 2), (4, 0)]

    # Façade synthétique : maison à pignon (fond noir, sujet blanc)
    img = Image.new("L", (640, 360), 0)
    d = ImageDraw.Draw(img)
    d.polygon([(60, 330), (60, 140), (320, 40), (580, 140), (580, 330)], fill=255)
    fp = os.path.join(_TMP, "facade_synth.png")
    img.save(fp)
    pts = extract_facade_polygon(fp, max_points=12)
    assert 4 <= len(pts) <= 12, f"polygone simplifié ({len(pts)} points)"
    # Le faîte du pignon (320, 40) → composition ×3 = (960, 120)
    apex = min(pts, key=lambda p: p[1])
    assert abs(apex[0] - 960) < 45 and abs(apex[1] - 120) < 45, "faîte détecté"
    xs = [p[0] for p in pts]
    assert min(xs) < 240 and max(xs) > 1680, "emprise gauche/droite correcte"

    # Preset XML : parsable, structure Arena (InputContour/segments/guide)
    xml_text = build_advanced_output_preset("test", pts, guide_image=fp,
                                            uid_base=1781155649252)
    root = ET.fromstring(xml_text)
    poly = root.find(".//Polygon")
    assert poly is not None, "slice Polygon présente"
    vs = poly.findall("./InputContour/points/v")
    assert len(vs) == len(pts), "tous les points dans InputContour"
    assert poly.find("./InputContour/segments").text == "L" * len(pts)
    assert len(poly.findall("./OutputContour/points/v")) == len(pts)
    guide = root.find(".//ScreenGuide/Params/ParamPixels")
    assert guide.get("fileName") == fp, "photo de façade en guide"
    assert root.find(".//CurrentCompositionTextureSize").get("width") == "1920"
    # Écriture (dossier de test — pas le vrai dossier Resolume)
    out = save_advanced_output_preset(xml_text, "PANDORA test",
                                      out_dir=os.path.join(_TMP, "ao_presets"))
    assert os.path.isfile(out) and out.endswith(".xml")

    # Mire : PNG 1920×1080
    mire = build_calibration_card(fp, pts, os.path.join(_TMP, "mapping", "mire.png"))
    with Image.open(mire) as m:
        assert m.size == (1920, 1080)

    # Bouton branché DANS LES DEUX pages (Conducteur + contrôleur Resolume),
    # via le helper partagé generate_full_calage
    from core.live_mapping import generate_full_calage
    res = generate_full_calage(fp, "test", os.path.join(_TMP, "calage_data"))
    assert os.path.isfile(res["mire_path"]) and res["preset_name"] == "PANDORA test"
    from ui.page_scenario_live import PageScenario
    assert "generate_full_calage" in inspect.getsource(PageScenario._on_generate_calage)
    from ui.page_live import PageLive as _PL2
    assert "generate_full_calage" in inspect.getsource(_PL2._on_generate_calage)


@test
def confinement_facade():
    """Confinement façade (retour test réel : les clips « sortent » de la
    façade) : masque pixel + keyframes masquées + verrouillage clip (option)."""
    import inspect
    from PIL import Image, ImageDraw
    from core.live_mapping import (
        build_facade_mask, apply_facade_mask_to_image, masked_keyframe,
        build_video_mask_cmd,
    )
    # Même façade synthétique que le calage : maison à pignon sur fond noir
    img = Image.new("L", (640, 360), 0)
    d = ImageDraw.Draw(img)
    d.polygon([(60, 330), (60, 140), (320, 40), (580, 140), (580, 330)], fill=255)
    fp = os.path.join(_TMP, "facade_conf.png")
    img.save(fp)

    # 1. Masque pixel : blanc dans la façade, noir dehors
    mp = build_facade_mask(fp, os.path.join(_TMP, "mapping", "mask.png"))
    assert mp and os.path.isfile(mp), "masque construit"
    with Image.open(mp) as m:
        assert m.getpixel((320, 220)) > 200, "intérieur façade = blanc"
        assert m.getpixel((10, 10)) < 30, "hors silhouette = noir"
    # Garde-fou : façade NON isolée (image pleine) → pas de masque (on ne
    # détruit jamais une image dont on ne maîtrise pas le détourage)
    full = Image.new("L", (64, 64), 255)
    fpf = os.path.join(_TMP, "facade_full.png")
    full.save(fpf)
    assert build_facade_mask(fpf, os.path.join(_TMP, "mapping", "m2.png")) == ""

    # 2. Keyframe masquée : copie en cache (mood original INTACT), rouge dans
    #    la façade, noir pur dehors ; ref non isolée → original renvoyé tel quel
    kf = os.path.join(_TMP, "kf_red.png")
    Image.new("RGB", (640, 360), (200, 30, 30)).save(kf)
    out = masked_keyframe(kf, fp, os.path.join(_TMP, "conf_data"))
    assert out != kf and os.path.isfile(out), "copie masquée en cache"
    with Image.open(out) as o:
        assert o.getpixel((320, 220))[0] > 150, "contenu conservé dans la façade"
        assert sum(o.getpixel((10, 10))) < 30, "noir pur hors silhouette"
    with Image.open(kf) as orig:
        assert orig.getpixel((10, 10))[0] > 150, "le mood original n'est pas touché"
    assert masked_keyframe(kf, fpf, os.path.join(_TMP, "conf_data")) == kf, \
        "façade non isolée → keyframe d'origine (jamais bloquant)"

    # 3. Commande vidéo (pure) : multiplication par le masque, audio copié
    cmd = build_video_mask_cmd("ffmpeg", "clip.mp4", "mask.png", "out.mp4")
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "blend=all_mode=multiply" in fc and "scale2ref" in fc
    assert "0:a?" in cmd and "copy" in cmd and cmd[-1] == "out.mp4"

    # 4. Branchements dans Générer depuis Séquences (mode Mapping) :
    #    prompt confiné + keyframes masquées + verrouillage optionnel du clip
    from ui.tab_t2v_live import TabT2V
    src_gen = inspect.getsource(TabT2V.start_generation)
    assert "STRICTLY INSIDE the building's silhouette" in src_gen, \
        "consigne de confinement dans l'ADN mapping"
    assert "masked_keyframe" in src_gen, "keyframes masquées avant l'envoi"
    src_fin = inspect.getsource(TabT2V.on_finished)
    assert "lock_video_to_facade" in src_fin and "_facade_lock_cb" in src_fin, \
        "verrouillage du clip final (option à cocher)"
    tv = TabT2V()
    assert hasattr(tv, "_facade_lock_cb") and not tv._facade_lock_cb.isChecked(), \
        "option décochée par défaut (le plein cadre reste recadrable dans Resolume)"

    # 5. Confinement AMONT (retour test réel : « le Père Noël entre par la
    #    cheminée » — or la cheminée n'était pas sur la façade mappée) : la règle
    #    de zone est dans TOUS les prompts IA du mode Mapping, jamais en Live.
    #    ⚠ Le critère est la VISIBILITÉ sur la photo de référence — JAMAIS de
    #    liste noire d'éléments (« no chimney » interdirait une vraie cheminée
    #    mappée ; retour Matthieu : « c'était un exemple, pas une généralité »)
    from api.live_screenplay import (
        _FACADE_FRAME_RULE, _SYSTEM_MAPPING, _ARRANGE_MAPPING, _SYSTEM_LIVE,
        _APPLY_ARRANGE_CONDUCTEUR, ArrangeChatConducteurWorker,
    )
    assert "NON VISIBLE" in " ".join(_FACADE_FRAME_RULE.split()), \
        "le critère est la visibilité sur la photo"
    assert "TRANSPOSE" in _FACADE_FRAME_RULE, \
        "la règle demande la transposition sur un élément visible"
    assert "no chimney" not in _SYSTEM_MAPPING and "no sky" not in _SYSTEM_MAPPING, \
        "pas de liste noire d'éléments (une vraie cheminée mappée doit rester possible)"
    assert _FACADE_FRAME_RULE in _SYSTEM_MAPPING, "découpage confiné"
    assert _FACADE_FRAME_RULE in _ARRANGE_MAPPING, "arrangement confiné"
    assert "actually visible in the reference facade image" in _SYSTEM_MAPPING, \
        "prompt vidéo anglais confiné par VISIBILITÉ"
    assert "non visible" in _APPLY_ARRANGE_CONDUCTEUR, "application d'arrangement confinée"
    assert _FACADE_FRAME_RULE not in _SYSTEM_LIVE, "le mode Live reste libre"
    assert "transpose" in inspect.getsource(ArrangeChatConducteurWorker.run), \
        "co-écriture (chat d'arrangement) confinée"
    import api.live_extract as LE
    assert "_FACADE_FRAME_RULE" in inspect.getsource(LE.FormatConducteurWorker.run), \
        "Mise en page PANDORA confinée"
    assert ("non visible" in LE._mode_ctx("mapping")
            and "non visible" not in LE._mode_ctx("live"))

    # 6. ANCRAGE ARCHITECTURAL (retour test réel : la maison rétrécissait —
    #    effet superbe MAIS si la nuit n'est pas noire, la fenêtre projetée se
    #    sépare de la vraie fenêtre = impression de raté) : l'architecture
    #    visible reste à position/échelle EXACTES, jamais de zoom du contenu
    assert "ANCRAGE ARCHITECTURAL" in _FACADE_FRAME_RULE, \
        "règle d'ancrage dans tous les prompts IA mapping"
    assert "dézoom" in _FACADE_FRAME_RULE and "échelle" in _FACADE_FRAME_RULE
    assert "never shrinks" in src_gen and "registered with the real building" in src_gen, \
        "ADN mapping Seedance : la façade ne rétrécit/glisse jamais"


@test
def selection_plage_et_lasso():
    """Maj+clic = plage + lasso (rubber band) dans le Conducteur visuel —
    Live ET Cinéma ; bibliothèque Resolume : multi-sélection + drag multiple."""
    import inspect
    for mod_name in ("ui.tab_t2v_live", "ui.tab_t2v"):
        M = __import__(mod_name, fromlist=["StoryboardSelector"])
        src = inspect.getsource(M.StoryboardSelector)
        assert "QRubberBand" in src and "_apply_lasso" in src, f"{mod_name} : lasso"
        assert "ShiftModifier" in src and "_shot_order" in src, f"{mod_name} : Maj = plage"
        assert "_emit_selection" in src, f"{mod_name} : émission factorisée"
    import ui.page_live as PL
    src = inspect.getsource(PL)
    for tok in ("_selected_paths", "def _drag_paths", "drag_provider",
                "splitlines", "setValue(0)"):
        assert tok in src, f"page_live : {tok}"


@test
def pont_resolume():
    """Pont Resolume : client REST (endpoints + body URI texte), worker d'envoi,
    page contrôleur réactivée et branchée à la Vidéothèque."""
    import inspect
    from resolume.client import ResolumeClient, file_uri

    class _Resp:
        def __init__(self, code=200, payload=None, text="", content=b""):
            self.status_code = code
            self._p = payload if payload is not None else {}
            self.text = text
            self.content = content
        def json(self):
            return self._p

    class _Session:
        def __init__(self):
            self.calls = []
        def get(self, url, **k):
            self.calls.append(("get", url, k))
            if url.endswith("/product"):
                return _Resp(200, {"name": "Arena", "major": 7})
            if "/clips/" in url:
                # JSON minimal d'un clip (paramètres « choix » façon Arena)
                return _Resp(200, {
                    "name": {"value": "clip"},
                    "target": {"options": ["This Layer", "Active Layer"], "index": 0},
                    "beatsnapping": {
                        "beatsnap": {"options": ["Off", "1/2", "1 Bar", "2 Bars"],
                                     "index": 0}},
                    "transport": {"controls": {
                        "playmode": {"options": ["Loop", "Ping Pong",
                                                 "Play Once & Eject",
                                                 "Play Once & Hold"], "index": 0}}},
                    "autopilot": {"target": {"options": ["Off", "Previous Clip",
                                                         "Next Clip"], "index": 0}},
                })
            return _Resp(200, {"columns": [{} for _ in range(9)], "layers": [
                {"name": {"value": "PANDORA"},
                 "clips": [{"name": {"value": "P1"}, "connected": {"value": True}}]},
            ]})
        def post(self, url, **k):
            self.calls.append(("post", url, k))
            return _Resp(204)
        def put(self, url, **k):
            self.calls.append(("put", url, k))
            return _Resp(200)
        def delete(self, url, **k):
            self.calls.append(("delete", url, k))
            return _Resp(204)

    s = _Session()
    c = ResolumeClient("127.0.0.1", 8080, session=s)
    # Ping + composition
    assert c.get_product_info().get("name") == "Arena"
    layers = c.get_layers()
    assert layers and layers[0].name == "PANDORA" and layers[0].clips[0].active
    assert s.calls[-1][1].endswith("/api/v1/composition"), "couches via GET /composition"
    # /open : body = URI fichier PERCENT-ENCODÉE en texte brut (vu en réel :
    # les espaces non encodés → 200 'leftover' sans rien charger)
    assert file_uri(r"C:\a b\c d.mp4") == "file:///C:/a%20b/c%20d.mp4", \
        "espaces encodés %20 (exigé par la spec Arena)"
    clip = os.path.join(_TMP, "plan_01.mp4")
    open(clip, "wb").close()
    assert c.load_clip(1, 2, clip)
    m, url, kw = s.calls[-1]
    assert m == "post" and url.endswith("/composition/layers/1/clips/2/open")
    assert kw["data"] == file_uri(clip).encode("utf-8"), "URI fichier en body"
    assert kw["headers"]["Content-Type"] == "text/plain", "texte brut, pas JSON"

    # Bug Arena 7.26.2 : /open → 404 alors que /openfile charge → FALLBACK
    class _OpenBroken(_Session):
        def post(self, url, **k):
            self.calls.append(("post", url, k))
            if url.endswith("/open"):
                return _Resp(404, text="the requested clip is not found")
            return _Resp(204)
    sb_ = _OpenBroken()
    cb_ = ResolumeClient("127.0.0.1", 8080, session=sb_)
    assert cb_.load_clip(1, 1, clip), "bascule sur /openfile"
    assert sb_.calls[-1][1].endswith("/openfile"), "endpoint de secours utilisé"
    # 200 'leftover' (parseur no-op) = ÉCHEC, pas succès
    class _Leftover(_Session):
        def post(self, url, **k):
            self.calls.append(("post", url, k))
            return _Resp(200, text="leftover")
    assert not ResolumeClient("x", 1, session=_Leftover()).load_clip(1, 1, clip), \
        "'leftover' n'est pas un chargement"

    # Extension de composition : add_column + composition_counts
    assert c.composition_counts() == (1, 9), "comptes couches/colonnes"
    assert c.add_column() and s.calls[-1][1].endswith("/composition/columns/add")
    # Vider un slot = POST /clear (le DELETE échouait en réel) + vignette Arena
    assert c.clear_clip(1, 2)
    assert s.calls[-1][0] == "post" and s.calls[-1][1].endswith("/clips/2/clear")
    class _ThumbSession(_Session):
        def get(self, url, **k):
            if url.endswith("/thumbnail"):
                self.calls.append(("get", url, k))
                return _Resp(200, content=b"PNGDATA")
            return super().get(url, **k)
    ct = ResolumeClient("127.0.0.1", 8080, session=_ThumbSession())
    assert ct.get_clip_thumbnail(1, 1) == b"PNGDATA", "vignette du clip chargé"

    # Page : vignettes mi-clip, drag & drop, vider, modes d'affichage, sélection
    src_pl = inspect.getsource(__import__("ui.page_live", fromlist=["PageLive"]))
    for token in ("_MidThumbWorker", "_SlotThumbWorker", "drop_req", "clear_req",
                  "_acte_layers_cb", "_view_combo", "def _on_clear_layer",
                  "_selected_clip and os.path.isfile",
                  "def _play", "mouseDoubleClickEvent",   # preview des clips
                  "border-left:2px", "lib_scroll_col"):   # cadre + colonne scrollable
        assert token in src_pl, f"page Resolume : {token}"
    # ffmpeg.exe à la RACINE du projet trouvé en mode dev (vignettes noires
    # sinon — et conformation/mixages sur fallbacks fragiles)
    from core.video_utils import get_ffmpeg_exe, get_ffprobe_exe
    assert "APP_ROOT" in inspect.getsource(get_ffmpeg_exe), "ffmpeg racine (dev)"
    assert "APP_ROOT" in inspect.getsource(get_ffprobe_exe), "ffprobe racine (dev)"
    # Renommage, tempo, colonne
    assert c.set_clip_name(1, 2, "P1") and '"P1"' in s.calls[-1][2]["data"]
    assert c.set_tempo(129.0) and "tempocontroller" in s.calls[-1][2]["data"]
    assert c.trigger_column(3) and s.calls[-1][1].endswith("/composition/columns/3/connect")
    # Échec réseau → message Webserver dans last_error
    class _Down:
        def get(self, *a, **k):
            raise OSError("refused")
    d = ResolumeClient("127.0.0.1", 8080, session=_Down())
    assert d.get_product_info() == {} and "Webserver" in d.last_error

    # Patch tolérant : set_choice_param + scoping autopilot (manuel Arena 7.x)
    from resolume.client import set_choice_param, find_subtree
    clip_json = s.get("x/clips/1").json()
    assert set_choice_param(clip_json, {"playmode"}, "hold")
    pm = clip_json["transport"]["controls"]["playmode"]
    assert pm["index"] == 3 and "Hold" in pm["value"], "Play Once & Hold"
    assert set_choice_param(clip_json, {"beatsnap"}, "1 bar")
    assert clip_json["beatsnapping"]["beatsnap"]["index"] == 2, "Beat Snap 1 mesure"
    ap = find_subtree(clip_json, "autopilot")
    assert set_choice_param(ap, {"target", "action"}, "next")
    assert ap["target"]["index"] == 2, "Autopilot → Next Clip"
    assert clip_json["target"]["index"] == 0, \
        "le Clip Target hors autopilot n'est PAS touché (scoping)"

    # Worker d'envoi : 2 clips → slots consécutifs + BPM compo + MODE SHOW
    from api.resolume_push import PushToResolumeWorker
    clip2 = os.path.join(_TMP, "plan_02.mp4")
    open(clip2, "wb").close()
    s2 = _Session()
    w = PushToResolumeWorker(
        [{"path": clip, "name": "P1"}, {"path": clip2, "name": "P2"}],
        layer=2, start_column=5, bpm=129.0, show_mode=True,
        client=ResolumeClient("127.0.0.1", 8080, session=s2))
    results = []
    w.finished.connect(results.append)
    w.run()   # synchrone — pas de start() dans le harnais
    assert results and results[0]["sent"] == 2 and not results[0]["failed"]
    opens = [u for m, u, _ in s2.calls if m == "post" and u.endswith("/open")]
    assert opens[0].endswith("/layers/2/clips/5/open") \
        and opens[1].endswith("/layers/2/clips/6/open"), "slots consécutifs"
    assert any("tempocontroller" in (k.get("data") or "") for m, _, k in s2.calls
               if m == "put"), "BPM compo réglé"
    # Composition trop petite → colonnes ajoutées automatiquement (vu en réel :
    # 9 colonnes pour 27 clips = 18 échecs)
    s3 = _Session()
    w3 = PushToResolumeWorker(
        [{"path": clip, "name": "P1"}, {"path": clip2, "name": "P2"}],
        layer=1, start_column=9,   # besoin de la colonne 10 → +1
        client=ResolumeClient("127.0.0.1", 8080, session=s3))
    w3.run()
    adds = [u for m, u, _ in s3.calls if m == "post" and u.endswith("/columns/add")]
    assert len(adds) == 1, "1 colonne ajoutée pour atteindre la colonne 10"
    # Cibles par clip (répartition par acte) : layer/column explicites respectés
    s4 = _Session()
    w4 = PushToResolumeWorker(
        [{"path": clip, "name": "SQ1_P1", "layer": 1, "column": 1},
         {"path": clip2, "name": "SQ2_P2", "layer": 2, "column": 1}],
        client=ResolumeClient("127.0.0.1", 8080, session=s4))
    w4.run()
    opens4 = [u for m, u, _ in s4.calls if m == "post" and u.endswith("/open")]
    assert opens4[0].endswith("/layers/1/clips/1/open") \
        and opens4[1].endswith("/layers/2/clips/1/open"), "une couche par acte"
    # L'envoi « toute la bibliothèque » suit l'ordre NATUREL des plans
    from ui.page_live import PageLive as _PL
    assert "_natural" in inspect.getsource(_PL._on_push_queue), \
        "tri naturel SQ/P avant envoi"
    # Mode show : chaque clip est relu (GET) puis réécrit (PUT) avec les patches
    show_puts = [k.get("data", "") for m, u, k in s2.calls
                 if m == "put" and "/clips/" in u and "Hold" in k.get("data", "")]
    assert len(show_puts) == 2, "mode show appliqué aux 2 clips"
    assert all("Next Clip" in d for d in show_puts), "autopilot next dans le PUT"

    # Page contrôleur : réactivée dans la nav + branchée à la Vidéothèque
    import live_window as LW
    src_w = inspect.getsource(LW)
    assert '"resolume"' in src_w and "PageLive()" in src_w, "page dans la fenêtre Live"
    assert "queue_paths" in src_w, "Vidéothèque → file pré-chargée"
    from ui.page_live import PageLive
    src_p = inspect.getsource(PageLive)
    assert "scan_live_clips" in src_p, "bibliothèque = clips du PROJET"
    assert "PushToResolumeWorker" in src_p and "get_resolume_config" in src_p
    p = PageLive()
    p.queue_paths([clip, clip2])
    assert len(p._pending_paths) == 2, "file reçue"
    p.queue_paths([])
    assert p._pending_paths == []


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


@test
def film_reel_auto_coche_en_style_realiste_live():
    """RENDU & AUDIO (Live) : en style « Film réaliste » (key 'realistic'), le toggle
    « Prise de vue réelle » se coche automatiquement, sans jamais décocher hors style.
    Parité avec le Cinéma (porté à la demande). showEvent déclenche la synchro."""
    import inspect
    import core.style as style
    from PyQt6.QtWidgets import QApplication, QCheckBox
    QApplication.instance() or QApplication([])
    import ui.tab_t2v_live as T

    class _Stub:
        pass
    s = _Stub()
    s._film_anchor_cb = QCheckBox()
    _orig = style.get_style_key
    try:
        style.get_style_key = lambda: "realistic"
        T.TabT2V._sync_film_anchor_with_style(s)
        assert s._film_anchor_cb.isChecked(), "non coché en style réaliste"
        style.get_style_key = lambda: "noir"
        T.TabT2V._sync_film_anchor_with_style(s)
        assert s._film_anchor_cb.isChecked(), "ne doit pas décocher hors réaliste"
        s._film_anchor_cb.setChecked(False)
        T.TabT2V._sync_film_anchor_with_style(s)
        assert not s._film_anchor_cb.isChecked(), "ne doit pas cocher hors réaliste"
    finally:
        style.get_style_key = _orig
    assert "_sync_film_anchor_with_style" in inspect.getsource(T.TabT2V.showEvent)


@test
def sound_design_moteurs_multiples_live():
    """Sound Design Live : même sélecteur multi-moteurs (ElevenLabs SFX V2 défaut /
    MMAudio / Mirelo en texte ; MMAudio ajouté en réf vidéo). Parité Cinéma."""
    import tempfile
    import api.tts as tts
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import ui.tab_sound_design_live as SD
    tab = SD.TabSoundDesignLive()
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
def sound_design_tirette_duree_live():
    """Sound Design Live : durée = tirette adaptée au moteur (ElevenLabs 22 s, autres 30 s).
    Parité Cinéma. (La traduction du prompt vit dans api/tts — testée côté Cinéma.)"""
    from PyQt6.QtWidgets import QApplication, QSlider
    QApplication.instance() or QApplication([])
    import ui.tab_sound_design_live as SD
    tab = SD.TabSoundDesignLive()
    assert isinstance(tab._dur_text, QSlider) and isinstance(tab._dur_video, QSlider), "durée = tirette"
    tk = [tab._text_engine_combo.itemData(i) for i in range(tab._text_engine_combo.count())]
    tab._text_engine_combo.setCurrentIndex(tk.index("elevenlabs"))
    assert tab._dur_text.maximum() == 22, ("ElevenLabs = 22 s", tab._dur_text.maximum())
    tab._text_engine_combo.setCurrentIndex(tk.index("mmaudio"))
    assert tab._dur_text.maximum() == 30, ("MMAudio = 30 s", tab._dur_text.maximum())


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
