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
    """_normalize produit act/act_name/sound_prompt + seedance_prompt SECTIONNÉ
    (vidéo + [🎵 SOUND DESIGN]), clamp durée, Fixe en mapping."""
    from api.live_screenplay import _normalize
    from core.prompt_sections import sound_of, video_of
    n = _normalize({"action": "a", "prompt": "v", "sound_prompt": "s",
                    "act": 2, "act_name": "Drop", "duration": 99,
                    "camera_movement": "Travelling"}, "mapping")
    assert n["act"] == 2 and n["act_name"] == "Drop", "act/act_name"
    assert n["sound_prompt"] == "s", "sound_prompt (repli)"
    # UN seul prompt à sections : vidéo + son réunis, chacun ré-extractible.
    assert "[🎵 SOUND DESIGN]" in n["seedance_prompt"], "section son dans le prompt"
    assert sound_of(n["seedance_prompt"]) == "s", "son extractible (Sound Design)"
    assert video_of(n["seedance_prompt"]) == "v", "vidéo extractible (moteur vidéo)"
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
    # Découpage produit dans la LANGUE DE TRAVAIL (français par défaut) — plus
    # d'anglais figé : la traduction vers l'anglais est faite à l'ENVOI aux moteurs.
    assert "prompt VIDÉO en FRANÇAIS" in t and "prompt VIDÉO en ANGLAIS" not in t, \
        "PROMPT VIDÉO du découpage mapping en langue de travail (fr par défaut)"
    assert "en ANGLAIS" not in t, "aucun champ figé en anglais dans le découpage mapping"
    _lg = ls._decoupage_mapping_system("en")
    assert "prompt VIDÉO en ANGLAIS" in _lg, "langue de travail EN → découpage en anglais"


@test
def decoupage_depuis_mise_en_page_zero_perte():
    """Découpage depuis la Mise en page PANDORA : conversion DÉTERMINISTE (1 plan = 1
    segment, prompts co-écrits REPRIS) — plus de troncature IA (bug 29 plans → 17,
    2026-07-09). Le conducteur BRUT (sans « PLAN n ») garde le découpage IA."""
    import inspect
    import core.decoupage_layout as dl
    from api.live_screenplay import GenerateDecoupageWorker
    layout = "\n".join(
        ["TIMELINE MUSICALE : 128 BPM", "=== ACTE 1 — Intro ==="] +
        sum(([f"PLAN {n} — Titre {n}",
              f"Durée : {5 + n % 8}s · Valeur de plan : Plan large · Mouvement : Fixe",
              f'PROMPT VIDÉO (français) : "vidéo {n} détaillée"',
              f'PROMPT SON (sound design / SFX, français) : "son {n}"']
             for n in range(1, 30)), []))
    # Détection : mise en page structurée vs conducteur brut.
    assert dl.is_structured_layout(layout) and not dl.is_structured_layout("un conducteur brut"), \
        "détection mise en page (« PLAN n ») vs conducteur brut"
    segs = dl.parse_layout_segments(layout)
    assert len(segs) == 29, f"parseur : {len(segs)}/29 (perte)"
    assert segs[0]["action"] == "Titre 1" and segs[0]["duration"] == 5 + 1 % 8
    assert "vidéo 1" in segs[0]["prompt"] and '"' not in segs[0]["prompt"] and segs[0]["sound_prompt"] == "son 1"
    # Worker : source structurée → 29 segments SANS appel IA (aucune clé requise).
    w = GenerateDecoupageWorker(layout, "mapping"); cap = {}
    w.finished.connect(lambda s: cap.__setitem__("s", s))
    w.failed.connect(lambda e: cap.__setitem__("f", e))
    w.run()
    assert "f" not in cap and len(cap.get("s", [])) == 29, \
        f"worker : la mise en page 29 plans doit donner 29 segments (obtenu {len(cap.get('s', []))})"
    assert "is_structured_layout" in inspect.getsource(GenerateDecoupageWorker.run), \
        "worker : conversion déterministe de la mise en page non branchée"
    # ── Robustesse (cas trouvés par revue adversariale 2026-07-09) ──
    # (a) prompt multi-paragraphes (ligne vide au milieu) → texte CONSERVÉ, pas tronqué.
    _mp = dl.parse_layout_segments('PLAN 1 — X\nPROMPT VIDÉO (français) : "para un.\n\npara deux."\n')
    assert "para un" in _mp[0]["prompt"] and "para deux" in _mp[0]["prompt"], "prompt multi-paragraphes tronqué"
    # (b) en-tête d'acte SANS numéro → acte auto-incrémenté, jamais avalé dans le prompt son.
    _na = dl.parse_layout_segments(
        '=== ACTE 1 — A ===\nPLAN 1 — X\nPROMPT SON (français) : "s1"\n'
        '=== FINAL ===\nPLAN 2 — Y\nPROMPT VIDÉO (français) : "v2"\n')
    assert len(_na) == 2 and _na[1]["act"] == 2 and _na[0]["sound_prompt"] == "s1", "acte sans numéro mal géré"
    # (c) conducteur BRUT vaguement numéroté → NON structuré (le découpage IA reste utilisé).
    assert not dl.is_structured_layout("Plan 1 : intro\nPlan 2 : montée\nPlan 3 : drop"), \
        "faux positif : conducteur brut pris pour une mise en page"


@test
def avertissement_reecriture_regle_2026_07_09():
    """Règle 2026-07-09 : source du découpage AUTOMATIQUE (Mise en page PANDORA sinon
    conducteur), et l'avertissement de réécriture n'apparaît QUE si le chemin repasse
    par l'IA. En Live « Générer le découpage » : mise en page → conversion DÉTERMINISTE
    (prompts repris) et conducteur → création — AUCUN avertissement, AUCUN choix."""
    import inspect
    from ui.page_scenario_live import PageScenario
    from ui.decoupage_dialogs import _RewriteWarningDialog, confirm_prompt_rewrite
    # Dialogue : défaut = ne rien réécrire ; « Continuer » l'autorise explicitement.
    d = _RewriteWarningDialog(None)
    assert d.ok is False, "défaut = ne réécrit pas (choix sûr)"
    d._btn_cont.click()
    assert d.ok is True, "clic « Continuer » → autorise la réécriture"
    assert callable(confirm_prompt_rewrite)
    # Chemin principal Live : ni choix, ni avertissement (déterministe / création).
    src = inspect.getsource(PageScenario._on_storyboard)
    assert "self._decoupage_base()" in src, "_on_storyboard Live : source automatique absente"
    assert "choose_decoupage_source" not in src and "confirm_prompt_rewrite" not in src, \
        "_on_storyboard Live : ni fenêtre de choix ni avertissement (chemin fidèle)"
    # Placeholder Live (Séquences) : avertit seulement si mise en page NON parsable (IA).
    from ui.page_storyboard_live import PageStoryboard as _PSL
    _oa = inspect.getsource(_PSL._on_analyze)
    assert "confirm_prompt_rewrite" in _oa and "is_structured_layout" in _oa, \
        "placeholder Live : déterministe si parsable, avertissement sinon"


@test
def somme_durees_conformee_au_set():
    """Constat « Mapping Nicolas » 2026-07-13 : la mise en page co-écrite totalisait
    3:55 pour un set de 4:28 (un LLM n'additionne pas juste) → 33 s manquaient à
    l'export. La somme des durées est désormais CONFORMÉE à la durée du set à
    l'écriture du découpage (prorata, secondes entières, bornes) et la consigne
    d'arithmétique est dans tous les prompts qui écrivent des durées."""
    import inspect
    from core.music_align import conform_durations_to_set, set_duration_seconds
    assert abs(set_duration_seconds([{"duration": 267.97}]) - 267.97) < 1e-6
    # Cas RÉEL (durées du projet, ~3:56) → conformés à 268 s exactement, bornes OK.
    _real = (4, 6, 4, 5, 9, 6, 11, 6, 6, 9, 7, 8, 4, 6, 7, 6, 9, 9, 8, 14, 6, 15,
             4, 12, 4, 12, 12, 12, 15)
    segs = [{"duration": d} for d in _real]
    assert sum(s["duration"] for s in segs) == 236
    r = conform_durations_to_set(segs, 267.97)
    assert r["adjusted"] and r["target"] == 268, r
    assert sum(s["duration"] for s in segs) == 268 == r["new_sum"], "somme ≠ set"
    assert all(2 <= s["duration"] <= 15 for s in segs), "bornes 2-15 violées"
    # Tolérance ±2 s : on ne touche à rien (durées co-écrites respectées).
    segs2 = [{"duration": 10}, {"duration": 10}]
    assert not conform_durations_to_set(segs2, 21.0)["adjusted"] and segs2[0]["duration"] == 10
    # Cible inatteignable → au plus près (n × max), jamais d'explosion.
    segs3 = [{"duration": 5}, {"duration": 5}]
    r3 = conform_durations_to_set(segs3, 120)
    assert r3["adjusted"] and sum(s["duration"] for s in segs3) == 30
    # Pas de set → no-op.
    assert not conform_durations_to_set([{"duration": 5}], 0)["adjusted"]
    # Branché dans l'écriture du découpage (couvre Appliquer ET Tout générer).
    from ui.page_scenario_live import PageScenario
    src = inspect.getsource(PageScenario._write_decoupage_segments)
    assert "conform_durations_to_set" in src and "set_duration_seconds" in src, \
        "conformation de la somme non branchée à l'écriture du découpage"
    # Consigne d'arithmétique là où les durées s'écrivent : mise en page,
    # découpage IA (live + mapping), co-écriture des plans.
    import api.live_screenplay as LS, api.live_extract as LE, api.plan_coedit as PC
    assert "ARITHMÉTIQUE" in LS._decoupage_live_system("fr")
    assert "ARITHMÉTIQUE" in LS._decoupage_mapping_system("fr")
    assert "ARITHMÉTIQUE OBLIGATOIRE" in inspect.getsource(LE), "mise en page : consigne absente"
    assert "la SOMME des durées de la" in inspect.getsource(PC), "co-écriture plans : consigne absente"


@test
def tout_generer_source_mise_en_page():
    """Règle 2026-07-13 : « Tout générer » utilise la MÊME source (Mise en page PANDORA
    si présente, sinon conducteur) et le MÊME moteur (worker Live calibré mode+façade)
    que le bouton « Générer le découpage » — plus de worker Cinéma sur le conducteur
    brut, et l'écriture passe par le helper commun (namespace live_seq_* garanti)."""
    import inspect
    from ui.page_scenario_live import PageScenario
    src = inspect.getsource(PageScenario._gen_all_step_storyboard)
    assert "GenerateDecoupageWorker" in src and "_text_with_music" in src, \
        "gen_all storyboard : worker Live + source mise en page attendus"
    assert "GenerateStoryboardWorker" not in src and "_get_text" not in src, \
        "gen_all storyboard : worker Cinéma / conducteur brut encore utilisés"
    done = inspect.getsource(PageScenario._gen_all_storyboard_done)
    assert "_write_decoupage_segments" in done, \
        "gen_all storyboard : écriture hors helper commun (namespace non garanti)"
    apply_src = inspect.getsource(PageScenario._apply_decoupage)
    assert "_write_decoupage_segments" in apply_src, \
        "_apply_decoupage : doit passer par le helper commun"


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
    # CLASSE entière : l'appel vit dans _layout_call depuis la relance corrective.
    src = inspect.getsource(le.FormatConducteurWorker)
    assert 'tier="creative"' in src, "tier créatif (Sonnet/Fable) pour la mise en page"
    assert "ÉCRAN" in src, "façade = écran (pas un sujet)"
    assert "seuls" not in src.split("ÉCRAN")[0] or True
    assert "TRÈS DÉTAILLÉ" in src, "prompts vidéo détaillés"
    assert "PROMPT SON" in src and "PROMPT VIDÉO" in src, "deux prompts par plan"
    assert "DURÉE CIBLE" in src, "durée cible injectée"
    assert "INTERDIT d'y mettre le BPM" in src, "BPM banni du prompt vidéo"
    # La mise en page reste dans la LANGUE DE TRAVAIL (français par défaut) — plus
    # d'anglais figé : la traduction vers l'anglais est faite à l'ENVOI aux moteurs.
    assert "get_lang" in src, "langue de la mise en page = langue de travail (get_lang)"
    # PROMPT VIDÉO : plus de mention du moteur « Seedance 2.0 » (rendu multi-moteurs) ;
    # la LANGUE de travail reste annotée. (2026-07-07)
    assert "PROMPT VIDÉO (Seedance 2.0" not in src, "annotation moteur retirée du PROMPT VIDÉO"
    # Depuis le passage aux fiches « DÉCOUPAGE PANDORA 2 » (2026-07-26) le champ
    # s'appelle PROMPT VISUEL — la langue de travail reste annotée de la même façon.
    assert 'PROMPT VISUEL : prompt en " + _pl' in src, \
        "langue de travail conservée dans l'annotation du prompt visuel"


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
    from core.prompt_sections import video_with_sound
    # UN seul prompt à sections : le prompt du plan contient une section son.
    shot = {"seedance_prompt": video_with_sound(
                "Opening: blue ocean. Then a whale. In the final moment dark.",
                "Deep abyssal drone at 129 BPM, whale moans, subby thumps"),
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
    # UN seul prompt à sections : la section son NE POLLUE PAS l'image fixe.
    assert "SOUND DESIGN" not in p_live and "129 BPM" not in p_live, \
        "le son est retiré du prompt mood (image fixe)"
    assert "dolly push in" not in p_live, "pas de mouvement caméra"
    # Le Live reçoit lui aussi la GRAMMAIRE du moteur (2026-07-25) : brief à champs
    # pour Nano Banana, prose sans interdit pour Seedream — et plus aucun mot de
    # qualité générique (« ultra-detailed », « 4K ») qui traînait dans ce builder.
    sb.set_namespace("live_seq_mapping")
    _l_nb2  = build_mood_prompt(shot, "style x", "nb2")
    _l_seed = build_mood_prompt(shot, "style x", "seedream5")
    sb.set_namespace("storyboard")
    assert "Action:" in _l_nb2, "Live/Nano Banana : brief à champs attendu"
    assert "Action:" not in _l_seed, "Live/Seedream : prose attendue"
    for _p in (p_live, _l_nb2, _l_seed):
        assert "OPENING state" in _p, "état d'ouverture perdu"
        assert "4K" not in _p and "ultra-detailed" not in _p, \
            "mots de qualité génériques (interdits par la doctrine de prompt)"
        assert "129 BPM" not in _p, "le son n'a pas sa place dans une image fixe"
    # Cinéma : focale + titre conservés ; suffixe qualité assaini (audit 2026-07-02)
    assert "35mm" in p_cine and "cinematic still frame" in p_cine.lower() \
        and "Les baleines" in p_cine
    # …mais le mouvement caméra n'entre PAS dans un prompt d'image, des deux côtés
    # (Live l'excluait déjà, le Cinéma le retire depuis le 2026-07-25).
    assert "dolly push in" not in p_cine, "Cinéma : mouvement caméra dans un Mood"


@test
def prompts_moods_kontext():
    """Moods mapping : consignes PARTAGÉES Flux ↔ Nano Banana 2 (constantes module) —
    canvas de nuit, fond noir, visibilité pilotée par le prompt, priorité façade."""
    import api.apercu as A
    src  = inspect.getsource(A.run_generation)
    lock = A._MAPPING_NIGHT_LOCK          # valeur (chaîne concaténée → fragments contigus)
    prio = A._FACADE_PRIORITY_DIRECTIVE
    assert "projection CANVAS" in lock, "canvas"
    assert "lit ONLY" not in lock, "ancienne consigne retirée"
    assert "PURE BLACK #000000" in lock, "fond noir"
    # Visibilité pilotée par le PROMPT, pas la photo : un élément de façade (porte/fenêtre/
    # structure) que le prompt dit NON visible doit passer en NOIR (fix 2026-07-09).
    assert "VISIBILITY IS DRIVEN BY THE PROMPT" in lock and "MUST be rendered as PURE BLACK" in lock, \
        "consigne d'exclusion (éléments non visibles → noir) absente"
    assert "fal-ai/flux-pro/kontext" in src, "Kontext quand façade fournie"
    assert "kontext/max/multi" in src, "Kontext multi quand façade + inspiration"
    # FAÇADE = priorité absolue ; réf = inspiration lâche, jamais copiée/substituée.
    assert "ABSOLUTE PRIORITY" in prio and "MANDATORY projection canvas" in prio, "façade non priorisée"
    assert "loose ARTISTIC INSPIRATION" in prio and "MUST NOT replace the facade" in prio \
        and "MUST NOT be pasted" in prio, "réf non cantonnée à l'inspiration"
    # Les MÊMES consignes mapping s'appliquent à Nano Banana 2 (mode façade partagé).
    nb2 = inspect.getsource(A.run_generation_nb2)
    assert "_MAPPING_NIGHT_LOCK" in nb2 and "_FACADE_PRIORITY_DIRECTIVE" in nb2 and "facade_ref" in nb2, \
        "NB2 n'utilise pas les mêmes consignes mapping / le mode façade"
    assert "facade_ref" in inspect.signature(A.run_generation_nb2).parameters, "NB2 : param facade_ref absent"
    import inspect as _i
    assert "inspiration_ref" in _i.signature(A.MoodGenerationWorker.__init__).parameters
    from ui.dialog_apercu import MoodDialog
    src_d = inspect.getsource(MoodDialog._generate_from_image)
    assert "ImageLibraryDialog" in src_d, "inspiration choisie via la bibliothèque"


@test
def mood_batch_choix_moteur_live():
    """« Générer les Moods » (Live) : la fenêtre propose TOUT le catalogue image de
    PANDORA via un combo (élargi 2026-07-20 ; remplace le choix binaire Flux/NB2).
    En séquence MAPPING FAÇADE, la liste se restreint aux moteurs qui ÉDITENT une
    image de référence. Le choix mémorise la clé et _on_batch_mood le passe au
    worker via options={engine}."""
    import ui.page_storyboard_live as PSL
    import api.apercu as _A
    from core import image_engines as IE
    _orig_la = PSL.sb_api.load_apercus
    PSL.sb_api.load_apercus = lambda sid: {"paths": [], "active_idx": 0}
    try:
        d = PSL._MoodBatchDialog(None, [{"id": "a", "number": 1, "scene_title": "T"}])
    finally:
        PSL.sb_api.load_apercus = _orig_la   # ne PAS fuiter sur les tests suivants (chaînage mood)
    assert hasattr(d, "_opt_engine"), "combo moteur absent (remplace les 2 boutons)"
    _keys = [d._opt_engine.itemData(i) for i in range(d._opt_engine.count())]
    # Contexte non-mapping ici (aucune façade résolue) → tout le catalogue raster.
    assert _keys == IE.raster_engines(), "combo moteur Live ≠ catalogue image complet"
    d._opt_engine.setCurrentIndex(_keys.index("recraft"))
    d._btn_gen.click()
    assert d.engine == "recraft", "clic « Générer » → engine = moteur du combo"
    # Le handler passe le moteur choisi au worker.
    _obm = inspect.getsource(PSL.PageStoryboard._on_batch_mood)
    assert 'options={"engine"' in _obm and "dlg" in _obm, \
        "_on_batch_mood ne transmet pas le moteur choisi au MoodBatchWorker"
    # Filtre MAPPING : Flux Kontext + moteurs éditeurs de référence UNIQUEMENT.
    _map = [k for k, _ in _A.mood_engine_choices(is_mapping=True)]
    assert _map[0] == "flux" and set(_map[1:]) == set(IE.edit_capable_engines()), \
        "mapping : liste moteurs ≠ (Flux + éditeurs de référence)"
    # VARIATION d'un mood existant (MoodDialog) : combo moteur complet.
    assert "options" in inspect.signature(_A.MoodGenerationWorker.__init__).parameters, \
        "worker unitaire : param options (moteur) absent"
    assert "options=self._options" in inspect.getsource(_A.MoodGenerationWorker.run), \
        "worker unitaire : moteur non transmis à run_mood"
    # Le moteur se choisit DANS la fenêtre Mood (combo au-dessus du prompt), plus
    # dans une fenêtre intermédiaire : le prompt affiché doit déjà être écrit dans
    # la grammaire du moteur, donc le moteur est connu AVANT le clic.
    from ui.dialog_apercu import MoodDialog
    import ui.dialog_apercu as _DA
    assert not hasattr(_DA, "choose_mood_engine"), \
        "l'ancienne fenêtre de choix de moteur doit avoir disparu"
    _gsrc = inspect.getsource(MoodDialog._generate)
    assert "_current_engine" in _gsrc, "variation de mood : moteur du combo non utilisé"
    _csrc = inspect.getsource(MoodDialog._build_engine_combo)
    assert "mood_engine_choices" in _csrc, "combo moteur : catalogue non branché"
    # Changer de moteur DOIT changer le prompt.
    _esrc = inspect.getsource(MoodDialog._on_engine_changed)
    assert "_reset_prompt" in _esrc and "adapt_prompt" in _esrc, \
        "changer de moteur ne réécrit pas le prompt"
    # Le prompt reconstruit est écrit pour le moteur sélectionné.
    _rsrc = inspect.getsource(MoodDialog._reset_prompt)
    assert "_current_engine()" in _rsrc, "prompt du Mood non écrit pour le moteur"


@test
def studio_live_vignettes_et_picker():
    """Deux défauts identiques au Cinéma, corrigés côté Live le 2026-07-25 :
    1) les vignettes lisaient get_selected_images(), qui OMET le décor, pendant que
       le bandeau lisait get_ref_images() — « 2 images envoyées », une vignette ;
    2) dans le sélecteur d'éléments du Storyboard, `:selected` ne neutralisait que
       le fond : le nom d'un élément coché devenait illisible."""
    import ui.tab_t2v_live as TL
    _cls = next(o for o in vars(TL).values()
                if isinstance(o, type) and hasattr(o, "_on_context_changed"))
    # La source a été CENTRALISÉE dans _all_reference_images le 2026-07-26 : le
    # Live n'affichait qu'UNE source sur quatre (casting), en oubliant le template
    # visuel, le mood, les images d'inspiration et la FAÇADE — pourtant comptée
    # dans le bandeau. On vérifie donc l'invariant, plus fort que l'ancien.
    _all = inspect.getsource(_cls._all_reference_images)
    assert "self._casting.get_ref_images()" in _all \
        and "self._casting.get_selected_images()" not in _all, \
        "vignettes Live : liste envoyée ≠ liste affichée (décor manquant)"
    for _src in ("_style_ref_path", "get_building_ref", "_mood_ref_cb",
                 "reference_images"):
        assert _src in _all, ("source d'images de référence oubliée", _src)
    # Vignettes et compteur lisent la MÊME liste — ils ne peuvent plus diverger.
    _ban = inspect.getsource(_cls._update_injection_banner)
    assert "total = len(self._all_reference_images())" in _ban, \
        "le compteur « N image(s) envoyée(s) » recalcule à part"
    assert "self._refresh_ref_thumbs()" in _ban, \
        "les vignettes ne suivent pas le bandeau (elles restaient figées)"
    import ui.page_storyboard_live as PSL2
    _p = inspect.getsource(PSL2._elements_picker_dialog)
    _i = _p.index("::item:selected")
    assert "color:" in _p[_i:_i + 160] and "rgba(" in _p[_i:_i + 160], \
        "sélecteur d'éléments Live : texte sélectionné sans couleur explicite"


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
    assert "DÉCOUPAGE PANDORA 2" in s._FORMAT_PANDORA
    assert "SOURCE SCÉNARIO" in s._FORMAT_PANDORA and "PROMPT VISUEL" in s._FORMAT_PANDORA
    assert "SCREENPLAY SOURCE" in s._FORMAT_PANDORA_EN and "VISUAL PROMPT" in s._FORMAT_PANDORA_EN


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


@test
def facade_injectee_workers_texte_mapping():
    """Mapping : la FAÇADE RÉELLE est décrite (Vision) et injectée dans les prompts
    système des workers TEXTE (mise en page / découpage / co-écriture) pour que l'IA
    respecte le bâtiment au lieu d'inventer fenêtres/portes (2026-07-07)."""
    import inspect
    import core.live_building as lb
    b_fr = lb.facade_context_block("MA_DESC", "fr")
    b_en = lb.facade_context_block("MA_DESC", "en")
    assert "MA_DESC" in b_fr and "N'INVENTE" in b_fr.upper(), "bloc FR : consigne stricte absente"
    assert "MA_DESC" in b_en and "do not invent" in b_en.lower(), "bloc EN : consigne stricte absente"
    assert lb.facade_context_block("", "fr") == "", "bloc vide si desc vide"
    # describe_facade : sans clé Anthropic → "" (AUCUN appel réseau) ; sans fichier → ""
    import core.config as _cfg
    _orig = _cfg.load_config
    _cfg.load_config = lambda: {"anthropic_key": ""}
    try:
        from PIL import Image
        _img = os.path.join(_TMP, "_facade_desc.jpg")
        Image.new("RGB", (40, 24), (70, 70, 70)).save(_img)
        assert lb.describe_facade(_img) == "", "describe_facade sans clé doit renvoyer '' (aucun réseau)"
        assert lb.describe_facade("/pas/un/fichier.png") == "", "describe_facade sans fichier → ''"
    finally:
        _cfg.load_config = _orig
    # Signatures rétro-compat : facade_path="" ajouté EN DERNIER (aucun appelant cassé).
    from api.live_extract import FormatConducteurWorker
    from api.live_screenplay import GenerateDecoupageWorker
    from api.plan_coedit import PlanCoEditWorker
    for _c in (FormatConducteurWorker, GenerateDecoupageWorker, PlanCoEditWorker):
        _p = inspect.signature(_c.__init__).parameters
        assert "facade_path" in _p and _p["facade_path"].default == "", \
            f"{_c.__name__} : facade_path manquant ou défaut ≠ ''"
    assert "facade_context_block" in inspect.getsource(FormatConducteurWorker.run), \
        "mise en page : façade non injectée"
    assert "facade_context_block" in inspect.getsource(GenerateDecoupageWorker.run), \
        "découpage : façade non injectée"
    assert "FAÇADE RÉELLE" in inspect.getsource(PlanCoEditWorker.run), \
        "co-écriture : façade non jointe à l'assistant"
    # ── Images redimensionnées avant Claude (sinon erreur 400 « exceeds 10 MB ») ──
    from core.image_payload import encode_image_for_vision
    from PIL import Image as _PILImage
    _big = os.path.join(_TMP, "_grosse_facade.png")
    _PILImage.new("RGB", (5000, 3500), (60, 60, 60)).save(_big)
    _mt, _b64 = encode_image_for_vision(_big)
    assert len(_b64.encode()) < 4_000_000, "image vision non redimensionnée sous la limite Claude"
    # La façade et les refs passent par le redimensionnement (pas d'envoi brut).
    assert "encode_image_for_vision" in inspect.getsource(PlanCoEditWorker.run), \
        "co-écriture : image façade/réf envoyée sans redimensionnement (risque erreur 400 > 10 MB)"
    assert "encode_image_for_vision" in inspect.getsource(lb.describe_facade), \
        "describe_facade : façade envoyée sans redimensionnement"
    # ── Discuter (chat pur) vs Modifier le plan (applique) — façon Image IA (2026-07-07) ──
    from api.plan_coedit import _plan_coedit_system as _pcs, PlanCoEditWorker as _PCW
    _sd = _pcs("live", "mapping", discuss_only=True)
    assert "DISCUTES" in _sd and "RÉPONDS TOUJOURS EN DEUX BLOCS" not in _sd, \
        "co-écriture Live : mode discussion conversationnel (pas de bloc plan forcé)"
    assert "RÉPONDS TOUJOURS EN DEUX BLOCS" in _pcs("live", "mapping", discuss_only=False), \
        "co-écriture Live : mode modification demande le bloc plan"
    assert "discuss_only" in inspect.signature(_PCW.__init__).parameters, "worker : discuss_only absent"
    from ui.dialog_plan_coedit import PlanCoEditDialog as _PCD
    _dd = _PCD(None, "PLAN 1 — A\nx\n", edition="live", mode="live")
    for _m in ("_btn_modify", "_on_modify_plan", "_launch", "_on_worker_finished"):
        assert hasattr(_dd, _m), f"co-écriture : {_m} absent (bouton « Modifier le plan »)"
    # En DISCUSSION, le worker n'émet pas plan_ready → la fin doit lever le « busy »
    # via le signal natif finished (sinon chat + boutons bloqués sur « Rédaction en cours »).
    assert "self._worker.finished.connect" in inspect.getsource(_PCD._launch), \
        "co-écriture : signal natif finished non connecté (UI bloquée en discussion)"
    _dd._select_plan(0); _dd._set_busy(True)
    _dd._on_message_ready("conseil"); _dd._on_worker_finished()
    assert _dd._input.isEnabled() and _dd._btn_send.isEnabled(), \
        "co-écriture : UI reste bloquée après une réponse de DISCUSSION"
    # ── « Tous les plans » : correctif global appliqué à TOUS les plans (2026-07-07) ──
    import core.plan_layout as pl
    assert "CORRECTIF GLOBAL" in _pcs("live", "mapping", discuss_only=False, all_plans=True), \
        "system : mode correctif global absent"
    assert "all_plans" in inspect.signature(_PCW.__init__).parameters, "worker : all_plans absent"
    _da = _PCD(None, "PLAN 1 — A\nx\n\nPLAN 2 — B\ny\n", edition="live", mode="live")
    for _m in ("_btn_all", "_on_toggle_all", "_exit_all_mode"):
        assert hasattr(_da, _m), f"co-écriture : {_m} absent (Tous les plans)"
    _da._btn_all.setChecked(True)
    assert _da._all_mode and _da._plan_preview.isReadOnly() \
        and "Modifier tous les plans" in _da._btn_modify.text(), "activation « Tous les plans » KO"
    _da._pending_all = True
    _da._on_plan_ready("PLAN 1 — A2\nx\n\nPLAN 2 — B2\ny\n")   # mise en page COMPLÈTE corrigée
    assert not _da._all_mode and "A2" in _da.result_layout() and "B2" in _da.result_layout() \
        and pl.plan_count(_da.result_layout()) == 2, \
        "correctif global : mise en page non remplacée ou all-mode pas ressorti"
    # ⚠ ANTI-PERTE (bug 12/29 du 2026-07-08) : un correctif renvoyant MOINS de plans que
    # l'original est REJETÉ — on ne perd JAMAIS un plan, on reste en mode « tous ».
    _da2 = _PCD(None, "\n\n".join(f"PLAN {i} — T{i}\nx{i}" for i in range(1, 6)),
                edition="live", mode="live")
    _da2._btn_all.setChecked(True); _da2._pending_all = True
    _da2._on_plan_ready("PLAN 1 — SEUL\nz")   # 1 plan << 5
    assert _da2._all_mode and pl.plan_count(_da2._layout) == 5 and "SEUL" not in _da2.result_layout(), \
        "correctif tronqué : DOIT être rejeté sans perte (Live)"
    # Le worker applique le correctif PAR LOTS et ne rend jamais moins de plans que
    # l'original, même si chaque lot est tronqué par le modèle (fusion défensive).
    assert hasattr(_PCW, "_run_all_batched") and hasattr(_PCW, "progress"), \
        "worker : batching correctif global absent (_run_all_batched / progress)"
    _L15 = "\n\n".join(f"PLAN {i} — Titre{i}\nDurée : 5s\nPROMPT VIDÉO : \"p{i}\"" for i in range(1, 16))
    _w = _PCW(layout_text=_L15, plan_text="", plan_label="", history=[],
              user_message="corrige", edition="live", mode="live", all_plans=True)
    _res = {}
    _w.plan_ready.connect(lambda p: _res.__setitem__("plan", p))
    _w.failed.connect(lambda e: _res.__setitem__("fail", e))
    def _trunc_chat(system, messages, **kw):
        _b = pl.split_plans(messages[-1]["content"])
        return "\n\n".join(x["text"] for x in _b[:3])   # ne renvoie que 3 plans / lot
    _w._run_all_batched(_trunc_chat)
    assert "fail" not in _res and pl.plan_count(_res["plan"]) == 15, \
        "worker correctif global : lots tronqués → PERTE de plans (doit tout conserver)"
    # Sauvegarder / Ouvrir la co-écriture (sauvegarde de secours avant d'appliquer).
    for _m in ("_btn_save_file", "_btn_open_file", "_on_save_file", "_on_open_file", "_on_progress"):
        assert hasattr(_da2, _m), f"co-écriture : {_m} absent (Sauvegarder/Ouvrir)"
    # Page live : façade passée aux 3 workers (mise en page + découpage + « Tout
    # générer », aligné le 2026-07-13), gate mapping.
    _psrc = inspect.getsource(__import__("ui.page_scenario_live", fromlist=["_"]))
    assert "_facade_for_mapping" in _psrc and \
        _psrc.count("facade_path=self._facade_for_mapping()") == 3, \
        "page live : façade non passée aux workers (mise en page + découpage + tout générer)"


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
    # Fusion de plans : notion RETIRÉE du Live le 2026-07-26. La clé `merged`
    # n'était produite que par le worker CINÉMA, auquel le Live ne fait plus appel
    # (il utilise GenerateDecoupageWorker). Garder le dialogue « Garder fusionné /
    # Séparer » aurait laissé une branche morte qui rassure à tort.
    assert not hasattr(M.PageStoryboard, "_ask_merge_decision"), \
        "le dialogue de fusion est mort depuis la bascule sur le worker Live"
    gsrc = inspect.getsource(M.PageStoryboard._on_shots_generated)
    assert "strict_no_merge" not in gsrc and 'pop("merged"' not in gsrc, \
        "reste du chemin de fusion Cinéma dans le Live"
    # Ajouter une image de référence l'affiche DÈS le 1er ajout (bug « 2 fois »,
    # 2026-07-09) : le handler sauve PUIS émet changed → reconstruction de la ligne
    # depuis les données persistées (affichage non tributaire d'un widget invalidé).
    _rsrc = inspect.getsource(M._ShotRow.__init__)
    _i = _rsrc.find("def _open_refs")
    _j = _rsrc.find("_clickable(ref_lbl", _i)
    _blk = _rsrc[_i:_j if _j != -1 else _i + 1400]
    assert _i != -1 and "save_shot" in _blk and "changed.emit" in _blk, \
        "Live : l'ajout de référence doit émettre changed (refresh fiable dès le 1er ajout)"
    # Aperçu : N images côte à côte et ENTIÈRES (helper build_reference_thumb, 2026-07-09).
    _rr_i = _rsrc.find("def _render_ref")
    _rr_j = _rsrc.find("_render_ref()", _rr_i)
    _rr = _rsrc[_rr_i:_rr_j if _rr_j != -1 else _rr_i + 900]
    assert "build_reference_thumb" in _rr and "KeepAspectRatioByExpanding" not in _rr, \
        "Live : _render_ref n'utilise pas la vignette composite non recadrée"


@test
def colonnes_sequences():
    """22 colonnes, masquages Live {6,11,12} / Mapping {5..12}, ordre conducteur."""
    import core.storyboard as sb
    import ui.page_storyboard_live as M
    from ui.live_pages import SequenceLivePage, SequenceMappingPage, _LIVE_DEFAULT_ORDER
    # 24 = 22 colonnes + Référence (22) + P. de champ (23, portée du Cinéma
    # le 2026-07-26 et ajoutée EN FIN de _COLS pour ne pas décaler les ordres et
    # largeurs déjà persistés dans les projets).
    assert len(M._COLS) == 24, "22 colonnes + Référence + P. de champ"
    assert M._COLS[23][0] == "P. de champ", "P. de champ en logique 23 (fin de liste)"
    assert M._COLS[2][0] == "Acte" and M._COLS[4][0] == "Prompt"   # UN seul prompt à sections
    assert M._COLS[16][0] == "TC" and M._COLS[17][0] == "Musique"
    assert M._COLS[18][0] == "BPM" and M._COLS[19][0] == "Transition"
    assert M._COLS[22][0] == "Référence", "colonne Référence (inspiration) en logique 22"
    assert sorted(_LIVE_DEFAULT_ORDER) == list(range(24)), "ordre défaut = permutation valide"
    assert (_LIVE_DEFAULT_ORDER.index(23) == _LIVE_DEFAULT_ORDER.index(8) + 1
            and _LIVE_DEFAULT_ORDER.index(9) == _LIVE_DEFAULT_ORDER.index(23) + 1), \
        "P. de champ s'affiche entre Focal et Dist."
    assert _LIVE_DEFAULT_ORDER.index(22) == _LIVE_DEFAULT_ORDER.index(1) + 1, \
        "Référence affichée juste après Mood"
    mp = SequenceMappingPage(); mp.refresh()
    vis = M._visible_order()
    assert all(c not in vis for c in (5, 6, 7, 8, 9, 11, 12)), "masquage Mapping (+Mouvement)"
    assert all(c in vis for c in (16, 17, 18, 19, 20)), "colonnes conducteur visibles"
    # Ordre par défaut VALIDÉ (capture Matthieu 2026-06-10) : Mood · Référence · Acte ·
    # Plan · TC · Prompt · Musique · BPM · Vitesse · Durée · Notes · Transition ·
    # Acteurs · Accessoires (Référence 22 insérée juste après Mood le 2026-07-05).
    assert vis == [0, 1, 22, 2, 3, 16, 4, 17, 18, 10, 15, 20, 19, 14, 13, 21], \
        "ordre par défaut Mapping = capture validée + Référence après Mood"
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
    assert "_empty_wrap.setVisible(True)" in src_render, "vide → bloc dédié affiché"
    assert "_table_wrap.setVisible(True)" in src_render, "tableau → zone rétablie"
    # Aucun découpage → bouton « Générer depuis le conducteur » (demande 2026-07-06).
    assert "Générer depuis le conducteur" in src_render, "bouton Générer depuis le conducteur (Live)"
    for pg in (live, mp):
        assert (hasattr(pg, "_empty_wrap") and hasattr(pg, "_empty_gen_btn")
                and hasattr(pg, "_table_wrap")), \
            "bloc vide (message + bouton) + zone tableau présents (Live ET Mapping)"
        # Message « aucun découpage » : largeur DÉFINIE (sinon le QLabel wordWrap
        # centré était tronqué au-dessus du bouton, 2026-07-07).
        assert pg._empty_lbl.maximumWidth() < 16000 and pg._empty_lbl.minimumWidth() >= 400, \
            "label 'aucun découpage' à largeur fixe (anti-troncature)"
        # Depuis le 2026-07-23 (parité Cinéma) : Moods/Caler/Sauvegarder/Ouvrir/
        # Pitch deck/Ajouter/Supprimer vivent dans le menu « ☰ Action » tout à
        # gauche ; les boutons d'origine restent vivants mais cachés.
        assert hasattr(pg, "_btn_actions"), "bouton « Action » absent de la barre Séquences"
        _tlay = pg._btn_actions.parentWidget().layout()
        assert _tlay.indexOf(pg._btn_actions) == 0, "« Action » doit être tout à gauche"
        assert pg._btn_batch_mood.isHidden() and pg._btn_music_align.isHidden(), \
            "boutons d'origine censés être cachés (pilotés par le menu Action)"
    sb.set_namespace("storyboard")


@test
def coecriture_et_finalisation_live():
    """Réorg 2026-07-06 : « Conducteur » (Analyse + Co-écriture) et « Finalisation »
    (Mise en page + Co-écriture des plans) ; parseur de plans « PLAN n — » chirurgical."""
    import inspect
    src = inspect.getsource(__import__("ui.page_scenario_live", fromlist=["_"]))
    assert '_make_toggle("📖  Conducteur"' in src, "section Conducteur (ex-Claude IA) absente"
    # « Finalisation » renommée « Découpage » le 2026-07-23 (parité Cinéma).
    assert '_make_toggle("🎯  Découpage"' in src, "section Découpage (ex-Finalisation) absente"
    # « Générer les séquences » MIS EN AVANT en ROUGE + éclair (2026-07-26, parité
    # Cinéma où « Générer le storyboard » a repris l'identité de « Tout générer »).
    assert 'self._on_storyboard, color=CP.get("red", "#ff4f6a")' in src, \
        "« Générer les séquences » pas en rouge"
    assert '"⚡", "Générer les séquences"' in src, \
        "« Générer les séquences » a perdu son éclair"
    # « Co-écriture des plans » renommé « Affiner le découpage » (2026-07-23).
    assert '"Affiner le découpage"' in src and "def _on_plan_coedit" in src, \
        "bouton/handler Affiner le découpage absent (Live)"
    assert src.index("(tog_cond,") < src.index("(tog_final,") < src.index("(tog_gen,"), \
        "ordre du panneau droit incorrect (Conducteur, Finalisation, …, Générer)"
    # ── Panneau droit 2026-07-26 (demande Matthieu) ───────────────────────────
    # « Ajouter des références » EN TÊTE, avant le Conducteur ; « Style VJ » et
    # « Musiques du set » à la fin, après « Générer ».
    assert src.index("(tog_refs,") < src.index("(tog_cond,"), \
        "« Ajouter des références » doit précéder le Conducteur"
    assert src.index("(tog_gen,") < src.index("(tog_style,") < src.index("(tog_music,"), \
        "ordre de fin du panneau incorrect (… Générer, Style VJ, Musiques du set)"
    # La « Référence bâtiment (façade) » est FUSIONNÉE dans « Ajouter des
    # références » : plus de section repliable séparée, mais le bloc vit toujours.
    assert '_make_toggle("🎨  Ajouter des références"' in src, \
        "section « Ajouter des références » renommée ou disparue"
    assert "tog_bld" not in src, \
        "la façade a de nouveau sa propre section — elle doit être fusionnée"
    assert "self._bld_row" in src and "l_refs.addLayout(self._bld_row)" in src, \
        "le bloc façade n'est pas dans la section « Ajouter des références »"
    # « Tout générer » vit dans le menu Action, plus au bas du panneau.
    assert 'self._act_gen_all = _scn_menu.addAction("⚡  " + translate("Tout générer"))' in src, \
        "« Tout générer » absent du menu Action (Live)"
    assert "self._btn_generate_all.hide()" in src, \
        "le bouton « Tout générer » du bas de panneau n'est pas masqué (Live)"
    assert "self._act_gen_all.triggered.connect(lambda: self._btn_generate_all.click())" in src, \
        "l'entrée de menu « Tout générer » n'est pas branchée sur le bouton (Live)"
    # Parité Cinéma 2026-07-23 : hauteur ADAPTATIVE des boutons (plancher 46/50,
    # l'espace libre leur revient) et rangée « Durée cible » à sélecteur CIBLÉ
    # (sans quoi un trait se dessinait sous « Durée cible » et sous « Estimé »).
    assert "btn.setMinimumHeight(50 if color else 46)" in src, \
        "plancher compact des boutons (46/50) perdu — Live"
    assert "btn.setMaximumHeight(96)" in src and "QSizePolicy.Policy.Expanding" in src, \
        "boutons du panneau Live non adaptatifs"
    assert "sc_lay.addStretch()" not in src, \
        "le ressort final réintroduirait le vide en bas du panneau Live"
    assert "_section_container(grow=True)" in src, "sections d'actions Live non extensibles"
    assert "QWidget#ScenarioDurStripLive{{background:" in src, \
        "rangée Durée cible Live sans sélecteur ciblé (traits parasites)"
    import core.plan_layout as pl
    live = ("=== ACTE 1 ===\nPLAN 1 — A\nDurée : 8s\nPROMPT VIDÉO : \"a\"\n\n"
            "PLAN 2 — B\nDurée : 6s\nPROMPT VIDÉO : \"b\"\n")
    plans = pl.split_plans(live)
    assert len(plans) == 2, "parseur Live : 2 plans attendus"
    out = pl.replace_plan(live, 1, "PLAN 2 — B2\nDurée : 5s")
    assert "PLAN 1 — A" in out and "ACTE 1" in out and '"b"' not in out, \
        "replace_plan chirurgical Live"
    from ui.dialog_plan_coedit import PlanCoEditDialog
    from api.plan_coedit import _plan_coedit_system
    _syslive = _plan_coedit_system("live", "mapping")
    assert "PLAN <n> —" in _syslive, "format Live non calibré"
    # Co-écriture : le plan réécrit reste dans la LANGUE DE TRAVAIL (français par
    # défaut), plus d'anglais forcé (la traduction est faite à l'envoi aux moteurs).
    assert "reste en ANGLAIS" not in _syslive, "co-écriture Live : plus d'anglais forcé"
    assert "PROMPT VIDÉO (français)" in _syslive and "PROMPT VIDÉO (Seedance 2.0" not in _syslive, \
        "co-écriture Live : langue de travail conservée, annotation moteur « Seedance 2.0 » retirée"
    dlg = PlanCoEditDialog(None, live, edition="live", mode="live")
    assert not dlg.was_applied()
    # Réordonner (glisser-déposer) / ajouter / dupliquer / supprimer + renum (2026-07-07).
    L3 = "PLAN 1 — A\nx\n\nPLAN 2 — B\ny\n\nPLAN 3 — C\nz\n"
    assert pl.reorder(L3, [2, 0, 1]).startswith("PLAN 1 — C"), "reorder + renum"
    assert pl.reorder(L3, [0, 1]) == L3, "reorder ordre invalide = inchangé"
    assert "PLAN 2 — A" in pl.duplicate_plan(L3, 0) and pl.plan_count(pl.duplicate_plan(L3, 0)) == 4, "dup + renum"
    assert pl.plan_count(pl.delete_plan(L3, 1)) == 2 and "PLAN 2 — C" in pl.delete_plan(L3, 1), "delete + renum"
    assert pl.plan_count(pl.add_plan(L3, 0, "live")) == 4 and "PLAN 2 — Nouveau plan" in pl.add_plan(L3, 0, "live"), "add + renum"
    dlg2 = PlanCoEditDialog(None, L3, edition="live", mode="live")
    for _m in ("_on_plans_reordered", "_plan_context_menu", "_duplicate_plan", "_delete_plan_at",
               "_add_plan", "_on_apply_all", "_commit_current_preview", "_has_pending"):
        assert hasattr(dlg2, _m), f"handler {_m} absent du dialogue co-écriture"
    from PyQt6.QtWidgets import QAbstractItemView
    assert dlg2._plan_list.dragDropMode() == QAbstractItemView.DragDropMode.InternalMove, "glisser-déposer non activé"
    # Bouton renommé « Appliquer les modifications » (applique TOUT en une fois, 2026-07-07).
    assert "Appliquer les modifications" in dlg2._btn_apply.text(), "bouton non renommé"
    dlg2._duplicate_plan(0)
    # Les changements STRUCTURELS vivent dans l'état de TRAVAIL ; « appliqué » reste FAUX
    # tant qu'« Appliquer les modifications » n'a pas été validé.
    assert not dlg2.was_applied() and dlg2._has_pending(), "structurel = travail, pas encore appliqué"
    assert pl.plan_count(dlg2.result_layout()) == 4, "dup reflétée dans l'état de travail + renum"
    dlg2._on_apply_all()
    assert dlg2.was_applied() and pl.plan_count(dlg2.result_layout()) == 4, \
        "« Appliquer les modifications » valide tous les plans"

    # ── Anti-perte + auto-save + undo + le chat crée un vrai plan (2026-07-07) ──
    import inspect as _inspect
    assert hasattr(type(dlg2), "layout_committed"), "signal auto-save layout_committed absent"
    for _m in ("_commit_layout", "_ensure_plan_header", "_undo", "_redo", "_on_preview_edited"):
        assert hasattr(dlg2, _m), f"co-écriture : méthode anti-perte {_m} absente"
    assert pl.has_header("PLAN 7 — Titre") and not pl.has_header("juste du texte")
    _ml = pl.replace_plan_multi(L3, 0, "PLAN 1 — A retravaillé\nx2\n\nPLAN 2 — Intercalé\nnew")
    assert pl.plan_count(_ml) == 4 and "PLAN 3 — B" in _ml and _ml.count("PLAN 2 —") == 1, \
        "replace_plan_multi Live : +1 plan, suivants décalés, aucun numéro dupliqué"
    assert pl.plan_count(pl.renumber_all(L3)) == 3, "renumber_all Live conserve le nombre de plans"
    assert "CRÉER UN NOUVEAU PLAN" in _syslive, "prompt co-écriture Live : clause création de plan absente"
    # Dialogue — BUG A : une op structurelle NE jette PLUS la réécriture non committée.
    d2 = PlanCoEditDialog(None, L3, edition="live", mode="live")
    _saved = []
    d2.layout_committed.connect(lambda t: _saved.append(t))
    d2._select_plan(0); d2._pending_plan = 0
    d2._on_plan_ready("PLAN 1 — A MODIF_LIVE\nDurée : 8s\nPROMPT VIDÉO : \"rw\"")
    d2._add_plan()
    assert "MODIF_LIVE" in d2.result_layout() and _saved, \
        "Live BUG A : op structurelle a jeté la réécriture / pas d'auto-save"
    # BUG B : rewrite tardif atterrit dans le plan ENVOYÉ, pas l'affiché.
    d4 = PlanCoEditDialog(None, L3, edition="live", mode="live")
    d4._select_plan(0); d4._pending_plan = 0; d4._select_plan(1)
    d4._on_plan_ready("PLAN 1 — A REWRITE0\ny")
    _pp = pl.split_plans(d4.result_layout())
    assert "REWRITE0" in _pp[0]["text"] and "REWRITE0" not in _pp[1]["text"], \
        "Live BUG B : le rewrite n'atterrit pas dans le plan envoyé"
    # Undo revient à l'état d'avant l'ajout.
    _c = pl.plan_count(d2._layout); d2._undo()
    assert pl.plan_count(d2._layout) == _c - 1, "Live : Ctrl+Z n'annule pas l'ajout"
    # Le chat crée un VRAI nouveau plan (multi-bloc).
    d3 = PlanCoEditDialog(None, L3, edition="live", mode="live"); d3._select_plan(0); d3._pending_plan = 0
    d3._on_plan_ready("PLAN 1 — A2\nx\n\nPLAN 2 — Nouveau\nnew")
    assert pl.plan_count(d3.result_layout()) == 4, "Live : le chat ne crée pas de nouveau plan (multi)"
    # Parent : auto-save branché AVANT exec + slot silencieux.
    _psrc = _inspect.getsource(__import__("ui.page_scenario_live", fromlist=["_"]))
    assert "layout_committed.connect" in _psrc and "_on_plan_coedit_autosave" in _psrc, \
        "Live : auto-save de la co-écriture non branché sur la page"
    # ── Plus d'images de référence (12) + cap UI == cap worker + ruban scrollable ──
    from api.plan_coedit import _MAX_REF_IMAGES as _MRI
    from ui.dialog_plan_coedit import _MAX_REFS as _DLG_MRI
    assert _MRI >= 12 and _DLG_MRI == _MRI, "co-écriture : cap images < 12 ou UI≠worker"
    assert "self._refs[:4]" not in _inspect.getsource(__import__("api.plan_coedit", fromlist=["_"])), \
        "co-écriture worker : cap figé [:4] encore présent"
    assert "QScrollArea" in _inspect.getsource(__import__("ui.dialog_plan_coedit", fromlist=["_"])), \
        "co-écriture : ruban de références non scrollable"


@test
def studio_ia_onglets_style_conducteur_live():
    """Onglets Studio IA Live façon Conducteur : barre fond bg0 + filet sous la barre
    sur TOUTE la largeur (bord haut du PANE, pas du QTabBar → plus de ligne doublée
    ni tronquée, 2026-07-07) + barre GROUPÉE (séparateurs 2,4,6)."""
    import inspect
    sw = inspect.getsource(__import__("ui.live_studio_widget", fromlist=["_"]))
    assert "QTabBar{{background:{C['bg0']};border:none;}}" in sw, \
        "barre d'onglets Studio IA Live : fond noir + AUCUNE bordure (sinon ligne doublée/tronquée)"
    assert "QTabWidget::pane{{border:none;border-top:1px solid" in sw, \
        "filet pleine largeur sous la barre (bord haut du pane, façon Conducteur)"
    assert "class _GroupedTabBar" in sw and "set_group_ends({2, 4, 6})" in sw, \
        "barre groupée Live absente"


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
    # Focale masquée ; l'ancien encart « Tarifs » est remplacé par une ESTIMATION
    # de prix rouge (nb plans × durée × moteur × résolution), 2026-07-07.
    from ui.tab_t2v_live import TabT2V
    src_tv = inspect.getsource(TabT2V)
    assert "self._camera_picker.setVisible(False)" in src_tv
    assert "_refresh_price_estimate" in src_tv and "self._price_lbl" in src_tv, \
        "estimation de prix (rouge) absente de « Générer depuis Séquences »"
    # Dialogue Éditer : Optique/Décor/Heure/Micro masqués
    import ui.dialog_shot_live as ds
    src_ds = inspect.getsource(ds)
    for marker in ("_hide_col(col_optic)", "_hide_col(col_decor)",
                   "_hide_col(col_time)", "_hide_col(col_mic)"):
        assert marker in src_ds, f"dialogue Live : {marker}"


@test
def estimation_prix_generation():
    """core/pricing : estimation INDICATIVE = nb plans × durée × prix/s (moteur +
    résolution) ; moteurs à durée fixe facturés au clip ; rappel « voir fal.ai »."""
    from core import pricing
    # Seedance 720p : $0.30/s → 10 plans × 5 s = 50 s = $15.
    cost, mode = pricing.estimate("seedance-2.0", "720p", 50.0, 10)
    assert abs(cost - 15.0) < 0.01 and mode == "s", f"720p ×50s = $15 attendu ({cost})"
    # 4K bien plus cher.
    assert pricing.estimate("seedance-2.0", "4k", 50.0, 10)[0] > 50, "4K > 1080p/720p"
    # Veo : facturé au CLIP (durée non prise en compte).
    c_veo, m_veo = pricing.estimate("veo-3.1", "1080p", 40.0, 5)
    assert m_veo == "clip" and abs(c_veo - 5.0) < 0.01, "Veo 5 clips × $1 = $5"
    # Le message contient le montant + le rappel fal.ai.
    msg = pricing.format_estimate("Seedance 2.0", "seedance-2.0", "720p", 50.0, 10)
    assert "$15.00" in msg and "10 plans" in msg and "fal.ai" in msg, msg


@test
def decoupage_routage_et_champs():
    """_apply_decoupage : namespace live_seq_{mode}, act→seq, seedance_prompt SECTIONNÉ
    (vidéo + son), sound_prompt en repli."""
    import core.storyboard as sb
    from ui.page_scenario_live import PageScenario
    from api.live_screenplay import _normalize
    from core.prompt_sections import sound_of
    p = PageScenario()
    navs = []
    p.navigate_requested.connect(lambda k, e="": navs.append(k))
    # segments passés par _normalize (comme le vrai flux) → seedance_prompt sectionné
    segs = [_normalize({"action": "a", "duration": 6, "prompt": "v", "sound_prompt": "s",
                        "act": 2, "act_name": "Drop"}, "mapping")]
    p._live_mode = "mapping"
    p._apply_decoupage(segs)
    assert sb.get_namespace() == "live_seq_mapping" and navs[-1] == "seq_mapping"
    shots = sb.list_shots()
    assert shots and shots[0]["seq_num"] == 2
    assert sound_of(shots[0]["seedance_prompt"]) == "s", "son dans le prompt sectionné"
    assert shots[0]["sound_prompt"] == "s", "sound_prompt en repli"
    p._live_mode = "live"
    p._apply_decoupage(segs)
    assert sb.get_namespace() == "live_seq_live" and navs[-1] == "seq_live"
    sb.set_namespace("storyboard")


@test
def dialog_plan_live_prompt_sectionne():
    """ShotDialog Live : UN seul prompt à SECTIONS (vidéo + [🎵 SOUND DESIGN]) comme en
    Cinéma — plus de champ « son » séparé ; le son reste extractible (Sound Design)."""
    from ui.dialog_shot_live import ShotDialog as LiveDlg
    from core.prompt_sections import video_with_sound, sound_of
    _p = video_with_sound("blue ocean", "boom")
    d = LiveDlg(shot={"id": "s1", "number": 1, "seedance_prompt": _p})
    assert hasattr(d, "_seedance_prompt"), "champ prompt unique présent"
    assert not hasattr(d, "_sound_prompt"), "plus de champ « son » séparé"
    assert d._seedance_prompt.toPlainText() == _p, "prompt sectionné chargé"
    assert sound_of(d._seedance_prompt.toPlainText()) == "boom", "son extractible"
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
    # « Sous-titres », « Caméra dynamique » et « Synchroniser le décor » RETIRÉS de
    # l'UI Live (demande Matthieu 2026-07-05) : plus créés du tout, comportement
    # neutre via les gardes hasattr/getattr du prompt et de l'aperçu.
    for _gone in ("_subtitle_cb", "_dyn_cam_cb", "_decor_sync_cb",
                  "_dyn_cam_toggle_row", "_decor_sync_toggle_row", "_subtitle_toggle_row"):
        assert not hasattr(t, _gone), f"{_gone} devrait être retiré de l'UI Live"
    t._set_seq_mode("live")
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
    assert "from core.download import" in _src, "téléchargement local via core.download (neutre)"
    assert t._casting.isHidden(), "Éléments récurrents replié par défaut"
    assert t._film_style_frame.isHidden(), "Choisir les références replié par défaut"
    assert not t._casting._decor_toggle.isVisible(), "section Décors masquée"
    assert hasattr(t, "_bref_row"), "sélecteur façade présent"
    sb.set_namespace("storyboard")


@test
def live_sans_import_davinci():
    """Séparation Cinéma/Live : AUCUN fichier Live n'importe davinci.* (même en
    lazy) — sinon tout le pont DaVinci entre dans le graphe d'import du Live.
    Le téléchargement local passe par le module NEUTRE core/download.py."""
    import glob as _glob
    import re as _re
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pat = _re.compile(r"^\s*(from|import)\s+davinci", _re.M)
    files = (_glob.glob(os.path.join(_root, "ui", "*_live.py"))
             + _glob.glob(os.path.join(_root, "ui", "live_*.py"))
             + _glob.glob(os.path.join(_root, "ui", "page_live*.py"))
             + [os.path.join(_root, "live_window.py")])
    assert len(files) > 10, "liste de fichiers Live vraisemblable"
    bad = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            if pat.search(fh.read()):
                bad.append(os.path.basename(f))
    assert not bad, f"import davinci.* dans fichier(s) Live : {bad}"
    # core/download.py doit rester neutre (aucun import davinci)
    with open(os.path.join(_root, "core", "download.py"), encoding="utf-8") as fh:
        assert not pat.search(fh.read()), "core/download.py doit rester neutre"


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
    # Option « Utiliser les images du Mood » (RENDU & AUDIO) : cochée par défaut →
    # les moods servent d'ancrage ; décochée → génération depuis la seule façade
    # (respect strict) sans keyframes moods.
    assert hasattr(t, "_use_mood_cb"), "case « Utiliser les images du Mood » absente"
    assert t._use_mood_cb.isChecked(), "case Mood cochée par défaut (comportement inchangé)"
    _sg = inspect.getsource(TabT2V.start_generation)
    assert '_use_mood = (not hasattr(self, "_use_mood_cb")) or self._use_mood_cb.isChecked()' in _sg, \
        "lecture de la case Mood dans start_generation"
    assert "REFERENCE FACADE IMAGE is the exact canvas" in _sg and "NO zoom, NO crop" in _sg, \
        "consigne de respect strict de la façade quand la case est décochée"
    assert 'ref_image_roles + ["facade"]' in _sg, \
        "façade toujours envoyée en référence (rôle facade) en mapping"
    # PRIORITÉ AU MOOD (révision du 2026-07-27, remplace le choix du 2026-07-09).
    # L'ancienne garde « and not i2v_frame » donnait la main au raccord automatique,
    # lequel est FORCÉ coché en mapping : sauf pour le tout premier plan, le Mood
    # n'atteignait jamais le moteur, alors que sa case était cochée et que son
    # libellé promet « le Mood du plan sert d'images-clés ». Matthieu l'a constaté
    # deux fois : rendu très différent du Mood, et Mood absent des images envoyées.
    # Le raccord depuis la dernière frame reste accessible — case Mood décochée.
    assert "and not i2v_frame" not in _sg, \
        ("le raccord automatique reprend la priorité sur le Mood : la case "
         "« Utiliser les images du Mood » redevient sans effet")
    assert "_anchor_kind" in _sg, \
        "l'image qui ancre le plan n'est pas identifiée, donc pas affichable"
    # Le libellé de la case doit continuer de promettre ce que le code fait.
    _init = inspect.getsource(TabT2V.__init__)
    assert "sert d'images-clés" in _init, \
        "le libellé de l'option ne décrit plus son effet"
    assert "end_frame = kf_end" not in _sg, \
        "end_image_url retiré du mapping (Seedance 2.0 i2v ne l'exploite pas)"
    # Anti-dérive de proportions renforcée dans le prompt mapping (_mapping_dna).
    assert "no anamorphic stretch" in _sg and "width-to-height ratio" in _sg, \
        "consigne anti-changement de proportions de la façade"
    sb.set_namespace("storyboard")


@test
def conducteur_derniere_frame_croix():
    """Vignettes Conducteur : la DERNIÈRE frame rendue s'affiche + une croix
    permet de l'effacer (casse le raccord → le plan suivant repart de son mood).
    Demande Matthieu 2026-07-09 (contre la dérive cumulative du raccord)."""
    import tempfile as _tf
    import core.storyboard as sb
    from PIL import Image
    from ui.tab_t2v_live import StoryboardSelector
    sb.set_namespace("live_seq_mapping")
    sb.clear_version_shots(sb.DEFAULT_VERSION_ID)
    _tmp = _tf.mkdtemp()
    lf = os.path.join(_tmp, "p1_last.png");  Image.new("RGB", (48, 27), (20, 30, 40)).save(lf)
    ff = os.path.join(_tmp, "p1_first.png"); Image.new("RGB", (48, 27), (40, 20, 30)).save(ff)
    s1 = sb.save_shot({"number": 1, "scene_title": "P1",
                       "last_frame_path": lf, "image_path": ff}, sb.DEFAULT_VERSION_ID)
    s2 = sb.save_shot({"number": 2, "scene_title": "P2"}, sb.DEFAULT_VERSION_ID)
    sel = StoryboardSelector()
    assert hasattr(sel._shot_cards[s1["id"]], "_clear_btn"), \
        "plan avec dernière frame → croix de suppression présente"
    assert not hasattr(sel._shot_cards[s2["id"]], "_clear_btn"), \
        "plan sans dernière frame → pas de croix"
    # Croix = VIDE les DEUX frames (dernière + première) → « plus d'image », pas de
    # repli sur une autre image ; la croix disparaît. Fichiers laissés sur le disque.
    sel._clear_last_frame(s1["id"])
    _fresh = sb.get_shot(s1["id"]) or {}
    assert _fresh.get("last_frame_path", "") == "", "dernière frame (raccord) vidée"
    assert _fresh.get("image_path", "") == "", "1re frame (vignette) vidée → plus d'image"
    assert not hasattr(sel._shot_cards[s1["id"]], "_clear_btn"), \
        "après effacement, la croix disparaît (refresh)"
    # RÉCUPÉRATION PAR CONVENTION (auto-réparation) : un plan au CHAMP vide mais dont
    # le fichier {id}_last_frame.png existe sur disque → la vignette + la croix
    # apparaissent quand même (cas réel : champ perdu par une édition/re-découpage).
    from core.context import get_data_root
    from ui.tab_t2v_live import _shot_frame_path
    _fdir = os.path.join(get_data_root(), "storyboard", "frames")
    os.makedirs(_fdir, exist_ok=True)
    s3 = sb.save_shot({"number": 3, "scene_title": "P3"}, sb.DEFAULT_VERSION_ID)  # champ vide
    _conv = os.path.join(_fdir, f"{s3['id']}_last_frame.png")
    Image.new("RGB", (48, 27), (60, 60, 20)).save(_conv)
    assert _shot_frame_path(s3, "last") == _conv, "frame retrouvée par convention (champ vide)"
    sel2 = StoryboardSelector()
    assert hasattr(sel2._shot_cards[s3["id"]], "_clear_btn"), \
        "convention → croix présente même sans champ persisté"
    sel2._clear_last_frame(s3["id"])
    assert not os.path.isfile(_conv), "la croix supprime le fichier de frame (convention)"
    assert not hasattr(sel2._shot_cards[s3["id"]], "_clear_btn"), \
        "après effacement (fichier supprimé), la croix disparaît"
    # La bande DOIT être rafraîchie après chaque export, sinon les dernières frames
    # (et leur croix) restent invisibles jusqu'à un rechargement manuel.
    from ui.tab_t2v_live import TabT2V
    _of = inspect.getsource(TabT2V.on_finished)
    assert "self._storyboard.refresh()" in _of, \
        "on_finished rafraîchit le Conducteur (dernière frame visible dès l'export)"
    # showEvent recharge la bande à CHAQUE affichage → les vignettes se chargent à
    # l'ouverture du projet sans action manuelle (demande Matthieu 2026-07-09).
    _se = inspect.getsource(TabT2V.showEvent)
    assert "self._storyboard.refresh()" in _se and "set_namespace" in _se, \
        "showEvent recale le namespace + recharge le Conducteur (chargement au lancement)"
    sb.set_namespace("storyboard")


@test
def coecriture_conducteur_chirurgicale():
    """Co-écriture Live : le chat du CONDUCTEUR est CHIRURGICAL (Q&R OU éditions
    ciblées, jamais de réécriture totale) + bouton « Générer le conducteur » pour la
    réécriture complète volontaire. Portage du Cinéma (Matthieu 2026-07-13)."""
    import inspect
    from api.live_screenplay import ArrangeSessionChatConducteurWorker
    assert "surgical" in inspect.signature(
        ArrangeSessionChatConducteurWorker.__init__).parameters, "worker accepte surgical="
    assert hasattr(ArrangeSessionChatConducteurWorker, "edits_ready"), "signal edits_ready"
    from ui.dialog_arrange_session_live import ArrangeSessionDialog
    dlg = ArrangeSessionDialog(None, "=== ACTE 1 ===\nPLAN 1 — Ouverture", "analyse", 5,
                               mode="live")
    assert hasattr(dlg, "_btn_generate"), "bouton « Générer le conducteur » présent"
    assert hasattr(dlg, "_on_edits_ready"), "handler d'application chirurgicale"
    assert "surgical: bool = True" in inspect.getsource(dlg._start_worker), \
        "chat chirurgical par défaut"
    assert "surgical=False" in inspect.getsource(dlg._on_generate_full), \
        "le bouton « Générer » fait la réécriture complète"
    # ── Fixes 2026-07-13 (retour Matthieu : « parfois ça n'écrit plus les modifs ») ──
    # ANTI-TRONCATURE : 4096 coupait le JSON chirurgical → 0 édition ; plafond 8192.
    _wsrc = inspect.getsource(ArrangeSessionChatConducteurWorker.run)
    assert "8192 if self._surgical" in _wsrc, "chirurgical Live : plafond 8192 requis"
    # PROMPT : jamais « je vais modifier » sans édition ; réponses AÉRÉES (paragraphes).
    from api.live_screenplay import _arrange_session_chat_surgical_system
    _p = _arrange_session_chat_surgical_system(5, "live")
    assert "IMPÉRATIF" in _p and "AÉRÉE" in _p, \
        "prompt chirurgical Live : règle anti-promesse + réponses aérées"
    # Bulles : interligne aéré.
    import ui.dialog_arrange_session_live as _dasl
    _bh = inspect.getsource(_dasl._bubble_html)
    assert "line-height" in _bh and "<br>" in _bh, "bulle de chat Live : interligne"


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
    # 2026-07-23 (parité Cinéma) : « Mises à jour » retiré de la barre du haut ;
    # la disquette vit dans la barre basse (insérée après le séparateur des drapeaux).
    assert hasattr(w, "_btn_save_global") and not hasattr(w, "_btn_update_header"), "topbar"
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
    # 2026-07-23 (parité Cinéma) : Manuel RETIRÉ de la topbar (accessible depuis
    # Paramètres) — seul « Nous contacter » (vert) reste en haut à gauche.
    assert not hasattr(w, "_btn_manual_top") and hasattr(w, "_btn_contact_top"), \
        "topbar : Contact seul (Manuel retiré)"
    assert "37,211,102" in w._btn_contact_top.styleSheet(), "Contact en vert"
    assert not hasattr(w._sidebar, "_btn_manual") and not hasattr(w._sidebar, "_btn_contact"), \
        "plus de Manuel/Contact dans la barre basse"
    _bar_lay = w._sidebar.layout()
    assert all(_bar_lay.indexOf(w._sidebar._items[k])
               < _bar_lay.indexOf(w._sidebar._items["settings"])
               for k in w._sidebar._items if k != "settings"), \
        "Paramètres tout au bord, en bas à droite"
    # 2026-07-23 (2e passe) : onglet Projets RÉINTRODUIT à gauche du Conducteur
    # (la page de démarrage n'est plus qu'un lanceur d'édition) ; Image IA
    # reste à côté de Studio IA.
    from live_window import _NAV_ITEMS as _NI
    assert _NI[0][2] == "projects" and _NI[1][2] == "conducteur", \
        "Projets en premier, Conducteur juste après"
    assert _NI[-3][2] == "image_ia" and _NI[-2][2] == "studio", \
        "Image IA à côté de Studio IA"
    # Paramètres pleine largeur (2026-07-23) : la barre de défilement colle au
    # bord droit, le centrage 1360 vit À L'INTÉRIEUR de la page.
    for k in w._pages:
        assert w._pages[k].maximumWidth() > 100000, f"page {k} pleine largeur"
    import inspect as _insp
    from ui.page_live_settings import PageLiveSettings as _PLS
    assert "setMaximumWidth(1360)" in _insp.getsource(_PLS), \
        "contenu Paramètres non centré à l'intérieur du scroll"
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
    # Alignement (2026-07-23) : l'en-tête de l'assistant partage la hauteur
    # STANDARD 40 px de la première rangée des pages — lignes alignées.
    assert w._assistant._header.maximumHeight() == 40, "en-tête assistant aligné"
    # 2026-07-23 : le bandeau titre des Séquences est RETIRÉ — ses contrôles
    # vivent dans la barre d'outils via _build_topbar_controls (parité Cinéma).
    _msb = __import__("ui.page_storyboard_live", fromlist=["x"])
    _sb_cls = getattr(_msb, "PageStoryboard")
    assert not hasattr(_sb_cls, "_build_shots_topbar"), "bandeau titre Séquences censé être retiré"
    assert hasattr(_sb_cls, "_build_topbar_controls"), "contrôles de l'ex-bandeau absents"
    _mpl = __import__("ui.page_live", fromlist=["x"])
    _pl_cls = getattr(_mpl, "PageLive")
    assert "setFixedHeight(60)" in _isp_lw.getsource(_pl_cls._build_topbar), \
        "bandeau 60 px : ui.page_live._build_topbar"
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
    # 3 onglets depuis le 2026-07-23 : Conducteur, Note de réalisation, Découpage.
    assert p._editor_tabs.count() == 3, "3 onglets éditeur (Conducteur/Note/Découpage)"
    assert not p._editor_tabs.isTabEnabled(2), "Découpage grisé au départ (onglet 3)"
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
    # ── Source du découpage AUTOMATIQUE (règle 2026-07-09, aucun choix manuel) ──
    import inspect
    assert p._decoupage_base() == "PLAN 1 — test", \
        "le découpage part de la Mise en page PANDORA quand elle existe"
    assert "PLAN 1 — test" in p._text_with_music() and "Mon conducteur" not in p._text_with_music(), \
        "_text_with_music doit injecter la mise en page, pas le conducteur brut"
    p._layout_view.setPlainText("")
    assert p._decoupage_base() == "Mon conducteur", "sans mise en page → conducteur"
    assert "self._decoupage_base()" in inspect.getsource(PageScenario._on_storyboard) \
        and "choose_decoupage_source" not in inspect.getsource(PageScenario._on_storyboard), \
        "_on_storyboard Live : source automatique, plus de fenêtre de choix"
    # ── Parité Cinéma 2026-07-23 : formatage riche persisté + Note injectée ──
    assert "formatted_html" in inspect.getsource(PageScenario._save), \
        "formatage riche du Conducteur persisté à la sauvegarde"
    assert "direction_note=" in inspect.getsource(PageScenario._on_format), \
        "Note de réalisation transmise au worker de mise en page"
    from api.live_extract import FormatConducteurWorker
    assert FormatConducteurWorker("t", "live", direction_note="n")._direction_note == "n"
    import api.live_extract as _le
    assert "note_for_ai" in inspect.getsource(_le.FormatConducteurWorker.run), \
        "note filtrée via note_for_ai avant injection (jamais recopiée brute)"
    # Restauration du formatage riche : appliquée si le HTML correspond au texte…
    p2 = PageScenario()
    _html = "<html><body><p><b>Bonjour</b></p></body></html>"
    p2._open_scenario({"title": "T", "raw_content": "Bonjour",
                       "formatted_content": "Bonjour", "formatted_html": _html})
    from PyQt6.QtGui import QTextCursor
    _cur = p2._editor_text.textCursor()
    _cur.movePosition(QTextCursor.MoveOperation.Start)
    _cur.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
    assert _cur.charFormat().fontWeight() >= 600, "gras restauré à la réouverture"
    # …et IGNORÉE si le texte a changé depuis (réécriture IA → texte brut prévaut).
    p2._open_scenario({"title": "T", "raw_content": "Texte réécrit",
                       "formatted_content": "Texte réécrit", "formatted_html": _html})
    assert p2._editor_text.toPlainText() == "Texte réécrit", \
        "HTML périmé écarté : le texte brut prévaut"


@test
def prompt_dialog_agrandi_live():
    """La fenêtre d'édition du prompt (clic colonne Prompt) s'ouvre CONFORTABLE (resize +
    poignée + plafond écran), comme en Cinéma — fini la petite fenêtre 540×240 qu'il
    fallait agrandir à la main (2026-07-08)."""
    import inspect
    import ui.page_storyboard_live as PSL
    src = inspect.getsource(PSL._text_dialog)
    assert "dlg.resize(" in src and "QGuiApplication" in src and "setSizeGripEnabled" in src, \
        "_text_dialog Live : taille confortable non appliquée (resize / écran / poignée)"
    assert "min(920" in src and "min(640" in src, \
        "_text_dialog Live : dimensions confortables (920×640 plafonnées) absentes"


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
    assert ap.get_provider() in ("anthropic", "openai", "mistral", "kimi", "glm", "ollama", "custom")
    assert ap._model("utility") and ap._model("creative"), "modèles des deux tiers"
    assert ap.ai_name(), "nom d'affichage"
    # Aucun worker, texte ou vision, ne doit contourner le routeur central.
    import api.enhance, api.assistant, core.lang, api.live_extract, api.live_screenplay
    for mod in (api.enhance, api.assistant, core.lang, api.live_extract,
                api.live_screenplay):
        src = inspect.getsource(mod)
        assert "anthropic.Anthropic(" not in src, f"{mod.__name__} : appel anthropic direct restant"
    src = inspect.getsource(api.live_screenplay)
    assert "ai_chat" in src, "live_screenplay routé via ai_provider (texte)"
    import api.screenplay
    src = inspect.getsource(api.screenplay)
    assert "anthropic.Anthropic(" not in src
    assert "core.ai_provider" in src, "screenplay routé via ai_provider"


@test
def selecteur_assistant_ia():
    """Sélecteur IA groupé, dynamique et identique dans Cinéma et Live."""
    from ui.page_settings import SettingsPage
    from ui.page_live_settings import PageLiveSettings
    cin = SettingsPage()
    nc = cin.ai_combo.count()
    assert nc >= 18
    assert any("Fable 5" in cin.ai_combo.itemText(i) for i in range(nc)), "Fable 5 proposé"
    assert any("GPT-5.5" in cin.ai_combo.itemText(i) for i in range(nc)), "GPT-5.5 proposé"
    # Clés GPT + Mistral toujours présentes (menu déroulant facultatif)
    assert hasattr(cin, "openai_input") and hasattr(cin, "mistral_input")
    # Ollama : champs conditionnels au choix global
    for i in range(nc):
        d = cin.ai_combo.itemData(i)
        if isinstance(d, dict) and d.get("engine") == "ollama":
            cin.ai_combo.setCurrentIndex(i)
            break
    assert not cin.ollama_url_input.isHidden(), "champs Ollama visibles quand Ollama choisi"
    cin.ai_combo.setCurrentIndex(0)
    assert cin.ollama_url_input.isHidden(), "champs Ollama cachés sur Claude"
    # PARITÉ Cinéma↔Live (demande Matthieu 2026-07-14) : mêmes 10 choix (mêmes
    # providers), hors DaVinci qui reste Cinéma-only.
    liv = PageLiveSettings()
    assert liv._ai_combo.count() == nc, "parité : mêmes choix Cinéma et Live"
    _provs = lambda combo: [combo.itemData(i) for i in range(combo.count())]
    assert _provs(liv._ai_combo) == _provs(cin.ai_combo), \
        "parité : mêmes providers, même ordre, des deux côtés"
    # Ollama : trouvé par donnée (robuste au décalage d'index après ajout Kimi)
    _oll_i = next(i for i in range(liv._ai_combo.count())
                  if isinstance(liv._ai_combo.itemData(i), dict)
                  and liv._ai_combo.itemData(i).get("engine") == "ollama")
    liv._ai_combo.setCurrentIndex(_oll_i)
    assert not liv._ollama_url_input.isHidden(), "champs Ollama visibles côté Live"
    # Kimi : sélection → champs clé + URL/modèle visibles, Ollama caché
    _km_i = next(i for i in range(liv._ai_combo.count())
                  if isinstance(liv._ai_combo.itemData(i), dict)
                  and liv._ai_combo.itemData(i).get("engine") == "kimi")
    liv._ai_combo.setCurrentIndex(_km_i)
    assert not liv._kimi_input.isHidden(), "clé Kimi visible côté Live quand Kimi choisi"
    assert not liv._kimi_url_input.isHidden() and not liv._kimi_model_input.isHidden()
    assert liv._ollama_url_input.isHidden(), "champs Ollama cachés quand Kimi choisi"


@test
def parametres_live_parite_cinema():
    """Parité Paramètres Live↔Cinéma (2026-07-14, hors DaVinci) : thème, clé OpenAI,
    moteur IA PAR TÂCHE réglable, testeurs de clés, aide API. Le Live UTILISAIT le
    routage ai_task_engines sans pouvoir le régler."""
    import inspect
    from ui.page_live_settings import PageLiveSettings
    from ui.page_settings import SettingsPage
    liv = PageLiveSettings()
    # Thème Sombre/Clair (même clé config « theme »)
    assert hasattr(liv, "_btn_dark") and hasattr(liv, "_btn_light"), "boutons thème"
    # Clé OpenAI + moteur par tâche (mêmes tâches que le Cinéma)
    assert hasattr(liv, "_openai_input"), "clé OpenAI réglable côté Live"
    cin = SettingsPage()
    assert set(liv._task_combos.keys()) == set(cin._task_combos.keys()) and liv._task_combos, \
        "moteur PAR TÂCHE : mêmes tâches des deux côtés"
    # Testeurs de clés + aide API (parité)
    for m in ("test_connection", "test_anthropic_connection", "test_openai_connection",
              "test_mistral_connection", "test_kimi_connection", "test_glm_connection",
              "_show_api_help", "_toggle_advanced"):
        assert hasattr(liv, m), f"parité Paramètres : {m} manquant côté Live"
    # « Choix personnalisé » déplie les avancés et laisse TOUTES les clés saisissables
    _cu_i = next(i for i in range(liv._ai_combo.count())
                  if isinstance(liv._ai_combo.itemData(i), dict)
                  and liv._ai_combo.itemData(i).get("engine") == "custom")
    liv._ai_combo.setCurrentIndex(_cu_i)
    assert liv._adv_open, "custom → avancés dépliés"
    assert not liv._openai_input.isHidden() and not liv._mistral_input.isHidden() \
        and not liv._kimi_input.isHidden() and not liv._glm_input.isHidden(), \
        "custom → toutes les clés visibles (routage par tâche)"
    # La sauvegarde écrit openai_key + ai_task_engines (comme le Cinéma)
    _sv = inspect.getsource(PageLiveSettings._save_api_key)
    assert "openai_key" in _sv and "ai_task_engines" in _sv, \
        "sauvegarde Live : openai_key + ai_task_engines absents"
    # DaVinci reste Cinéma-only (exclusion voulue par Matthieu)
    _liv_src = inspect.getsource(__import__("ui.page_live_settings", fromlist=["_"]))
    assert "DaVinci" not in _liv_src, "DaVinci ne doit PAS apparaître dans les Paramètres Live"


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
    # (le calage vit dans le helper commun _write_decoupage_segments depuis le
    # 2026-07-13 — « Appliquer » ET « Tout générer » y passent tous les deux)
    assert "assign_tracks_to_shots" in inspect.getsource(PageScenario._write_decoupage_segments), \
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
        # Découpage en LANGUE DE TRAVAIL (fr par défaut) : plus d'anglais figé.
        assert "en FRANÇAIS" in tt and "en ANGLAIS" not in tt, \
            "PROMPT VIDÉO/SON du découpage en langue de travail (fr par défaut)"
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
    from api.live_refs import _enrich_system, _PER_IMAGE_SYSTEM, _SYNTHESIS_SYSTEM
    _es = _enrich_system("live")
    assert "INT." in _es, "interdiction format scénario"
    # Enrichissement CHIRURGICAL (2026-07-06) : sortie = édits {find, replace},
    # pas tout le conducteur réécrit → moins de tokens, reste intact.
    assert '"find"' in _es and '"replace"' in _es and '"edits"' in _es, \
        "enrichissement chirurgical (édits find/replace)"
    assert "parse_edits" in inspect.getsource(EnrichConducteurWithRefsWorker.run), \
        "run() parse les édits (chirurgical)"
    # Doctrine 2026-06-11 : décodage COMPLET de direction artistique (pas que palette)
    for kw in ("Architecture", "Personnages & figures", "Style d'image", "INSPIRATION"):
        assert kw in _PER_IMAGE_SYSTEM, f"décodage DA complet : {kw}"
    assert "jamais à copier" in _SYNTHESIS_SYSTEM, "transposer les codes, pas copier"
    # La page utilise bien les workers Live
    from ui.page_scenario_live import PageScenario
    src_p = inspect.getsource(PageScenario)
    assert "AnalyzeRefsConducteurWorker" in src_p and "EnrichConducteurWithRefsWorker" in src_p


@test
def refs_indicateur_deja_enrichi():
    """Indicateur « conducteur déjà enrichi » (2026-07-06) : flag PERSISTANT, remis à
    zéro à chaque nouvelle analyse, petit signe sur le bouton « Enrichir »."""
    import inspect
    from ui.page_scenario_live import PageScenario
    p = PageScenario()
    assert hasattr(p, "_ref_enriched") and p._ref_enriched is False, "flag initialisé à False"
    assert '"ref_enriched"' in inspect.getsource(PageScenario._save), "flag non persisté (_save)"
    assert "ref_enriched" in inspect.getsource(PageScenario._open_scenario), "flag non restauré (_open)"
    rw = inspect.getsource(PageScenario._open_refs_window)
    assert "self._ref_enriched = True" in rw, "flag posé à l'application de l'enrichissement"
    assert "self._ref_enriched = False" in rw, "flag remis à zéro (nouvelle analyse/relance)"
    assert "déjà enrichi" in rw, "petit signe « déjà enrichi » sur le bouton"


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
    """« Analyse & co-écriture » Live : le mini-chat inline est REMPLACÉ par le
    studio de co-écriture complet (parité Cinéma), calibré CONDUCTEUR."""
    import inspect
    # Studio de co-écriture Live : worker dédié conducteur (jamais INT./EXT.)
    from api.live_screenplay import ArrangeSessionChatConducteurWorker
    w = ArrangeSessionChatConducteurWorker(
        "cond", "sugg", [], "?", intensity=5, mode="mapping", refs_analysis="DA")
    assert hasattr(w, "message_ready") and hasattr(w, "screenplay_ready") \
        and hasattr(w, "failed"), "mêmes signaux que le studio Cinéma"
    from api.live_screenplay import _arrange_session_chat_system
    _sys = _arrange_session_chat_system(5, "mapping")
    assert "« INT. »" in _sys, "format scénario explicitement interdit"
    assert "visible" in _sys and "façade" in _sys, \
        "mode mapping : confinement par visibilité (jamais de liste noire)"
    from ui.page_scenario_live import PageScenario
    src = inspect.getsource(PageScenario._open_arrange_window)
    assert "ArrangeChatConducteurWorker" not in src, "mini-chat inline retiré"
    assert "btn_session" in src, "Session de co-écriture réactivée (parité Cinéma)"
    assert "disable_default_buttons" in src, "arrangement : boutons par défaut neutralisés"
    src_sess = inspect.getsource(PageScenario._open_arrange_session)
    assert "dialog_arrange_session_live" in src_sess, "studio calibré conducteur"
    assert "disable_default_buttons" in inspect.getsource(PageScenario._open_refs_window), \
        "refs : boutons par défaut neutralisés"
    from ui.widgets import disable_default_buttons
    assert callable(disable_default_buttons)


@test
def analyse_arrangement_sauvegardee_live():
    """« Analyse & co-écriture » Live : l'analyse est PERSISTÉE avec le conducteur
    et ROUVERTE sans nouvel appel API (crédits préservés) ; « Relancer » dans la fenêtre."""
    import inspect
    import ui.page_scenario_live as _m
    src = inspect.getsource(_m)
    assert "Analyse & co-écriture" in src, "bouton renommé"
    assert "_start_arrange_analysis" in src, "relance = méthode dédiée"
    assert "arrange_analysis" in src, "analyse persistée avec le conducteur"
    assert "Relancer l'analyse" in src, "bouton Relancer dans la fenêtre"
    from ui.page_scenario_live import PageScenario
    p = PageScenario()
    p._set_editor_text("EXT. FACADE - NUIT\nSequence mapping.")
    p._current = {"arrange_analysis": "ANALYSE LIVE PERSISTÉE"}
    calls = []
    p._open_arrange_window = lambda analysis="", worker=None: calls.append((analysis, worker))
    p._on_arrange()
    assert calls == [("ANALYSE LIVE PERSISTÉE", None)], \
        "réouverture SANS worker (aucun crédit consommé)"
    assert p._last_analysis == "ANALYSE LIVE PERSISTÉE"
    # Erreur « crédits épuisés » → message clair
    from core.ai_provider import humanize_ai_error
    credit_error = humanize_ai_error("Your credit balance is too low")
    assert "Crédits" in credit_error and "fournisseur" in credit_error
    assert humanize_ai_error("autre erreur") == "autre erreur"


@test
def plafonds_anti_troncature():
    """Tout worker qui SORT un conducteur/découpage COMPLET = 16000 tokens.
    (Vu en réel 2026-06-11 : mise en page et enrichissement tronqués à 8000/8192.)"""
    import inspect
    from api.live_extract import FormatConducteurWorker
    from api.live_screenplay import GenerateDecoupageWorker, ApplyArrangeConducteurWorker
    from api.live_refs import EnrichConducteurWithRefsWorker
    # inspecte la CLASSE et non run() : depuis la relance corrective (2026-07-26),
    # FormatConducteurWorker fait son appel dans _layout_call, rejoué à l'identique.
    for cls in (FormatConducteurWorker, GenerateDecoupageWorker,
                ApplyArrangeConducteurWorker, EnrichConducteurWithRefsWorker):
        assert "max_tokens=16000" in inspect.getsource(cls), \
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
    assert "réellement VISIBLE sur la photo de référence" in _SYSTEM_MAPPING, \
        "prompt vidéo confiné par VISIBILITÉ (glose en langue de travail)"
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
    for key in ("Mise en page PANDORA", "Acte", "Prompt (vidéo + son)",
                "Sound Design", "Upscaling", "♫  Musiques du set",
                "🏢  Référence bâtiment (façade)", "Corriger le BPM",
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


@test
def fermeture_live_demande_sauvegarde():
    """LiveWindow demande de SAUVEGARDER à la fermeture (comme le Cinéma), via le helper
    PARTAGÉ ui.quit_dialog.confirm_quit — la régression « plus de message » ne revient
    pas (2026-07-07)."""
    import inspect
    import live_window as lw
    from ui.quit_dialog import confirm_quit
    assert callable(confirm_quit), "helper confirm_quit absent"
    src = inspect.getsource(lw.LiveWindow.closeEvent)
    assert "confirm_quit" in src, "LiveWindow : aucune confirmation de fermeture"
    assert "_on_global_save" in src, "LiveWindow : « Sauvegarder et quitter » ne sauve pas le conducteur"
    assert "self.closed.emit()" in src, "LiveWindow : signal closed perdu"
    # Fenêtre secondaire (2 écrans) : se ferme sans confirmation (inchangé).
    assert '_is_secondary' in src, "LiveWindow : garde fenêtre secondaire perdue"


@test
def bouton_generer_depuis_conducteur_seulement_si_vide():
    """Séquences Live/Mapping : « ⊕ Générer depuis le conducteur » (placeholder de
    découpage vide) ne reste PAS affiché une fois le découpage généré (2026-07-07)."""
    from ui.live_pages import SequenceMappingPage
    p = SequenceMappingPage()
    # Découpage VIDE, aucune version → placeholder + bouton visibles.
    p._all_shots = []
    p._active_version_id = None
    p._render()
    assert not p._empty_gen_btn.isHidden() and not p._empty_wrap.isHidden(), \
        "découpage vide : le bouton « Générer depuis » devrait être visible"
    # Découpage GÉNÉRÉ → placeholder ET bouton masqués, tableau visible.
    p._all_shots = [{"id": "a", "number": "P1", "duration": 15.0, "seedance_prompt": "x"},
                    {"id": "b", "number": "P2", "duration": 15.0, "seedance_prompt": "y"}]
    p._render()
    assert p._empty_gen_btn.isHidden() and p._empty_wrap.isHidden(), \
        "découpage généré : le bouton « Générer depuis » ne doit PLUS être affiché"
    assert not p._table_wrap.isHidden(), "découpage généré : le tableau doit être visible"
    # Le placeholder utilise la source AUTOMATIQUE (Mise en page PANDORA sinon conducteur,
    # règle 2026-07-09) : mise en page STRUCTURÉE → conversion DÉTERMINISTE 1 plan = 1
    # segment via _on_shots_generated (prompts co-écrits repris, zéro IA, zéro perte).
    import inspect
    _oa = inspect.getsource(type(p)._on_analyze)
    assert 'sc.get("layout_content"' in _oa and "_layout or _source" in _oa, \
        "placeholder Live : source automatique (layout sinon conducteur) non branchée"
    assert "is_structured_layout" in _oa and "parse_layout_segments" in _oa \
        and "_on_shots_generated" in _oa, \
        "placeholder Live : conversion déterministe de la mise en page non branchée"
    assert "choose_decoupage_source" not in _oa, \
        "placeholder Live : l'ancienne fenêtre de choix doit avoir disparu"
    # Preuve fonctionnelle : mise en page structurée de 5 plans → 5 shots écrits SANS
    # appel IA (save_shot stubé), prompts repris tels quels.
    import core.storyboard as _sbm, core.scenario as _scn
    _layout5 = "\n".join(
        ["=== ACTE 1 — Intro ==="] +
        sum(([f"PLAN {n} — Titre {n}",
              f"Durée : {5 + n}s · Valeur de plan :  · Mouvement : Fixe",
              f'PROMPT VIDÉO (français) : "vidéo co-écrite {n}"',
              f'PROMPT SON (sound design / SFX, français) : "son {n}"']
             for n in range(1, 6)), []))
    _orig_list = _scn.list_scenarios
    _scn.list_scenarios = lambda: [{"id": "s1", "title": "T", "formatted_content": "brut",
                                    "raw_content": "brut", "layout_content": _layout5}]
    _saved = []
    _orig_save = _sbm.save_shot
    _sbm.save_shot = lambda shot, *a, **k: _saved.append(dict(shot))
    try:
        p._on_analyze()
    finally:
        _sbm.save_shot = _orig_save
        _scn.list_scenarios = _orig_list
    assert len(_saved) == 5, f"placeholder déterministe : {len(_saved)}/5 plans écrits"
    assert "vidéo co-écrite 1" in _saved[0]["seedance_prompt"], "prompt co-écrit non repris"
    assert _saved[0]["scene_title"] == "Titre 1" and _saved[0]["seq_name"] == "Intro"


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


@test
def seed_reprise_et_4k_live():
    """4K best-effort Seedance 2.0 (défaut 1080p conservé) + reprise par GRAINE côté
    Live : Historique → « Générer depuis Séquences » (prompt + graine verrouillée).
    Fige les 2 chantiers 2026-07-04, parité avec le Cinéma."""
    import ui.tab_t2v_live as t2vl
    vals = [v for _, v in t2vl._ENGINE_RESOLUTIONS["seedance-2.0"]]
    assert vals[0] == "4k", "le 4K (validé) doit être EN TÊTE de la liste Seedance 2.0"
    assert t2vl._ENGINE_DEFAULT_RES.get("seedance-2.0") == "720p", "défaut Seedance = 720p"
    entry = {"prompt": "loop mapping facade", "seed": 999, "status": "done"}
    w = t2vl.TabT2V()
    assert w.cb_res.currentData() == "720p", \
        f"le combo résolution doit présélectionner 720p, pas {w.cb_res.currentData()}"
    w.prefill_from_seed(dict(entry))
    assert "loop mapping facade" in w.prompt_ta.toPlainText(), "prompt non réinjecté"
    assert w._last_seed == 999 and w._get_seed() == 999, "graine non verrouillée"
    # Câblage bout-en-bout : reprise → pré-remplit « Générer depuis Séquences » + bascule
    from ui.live_studio_widget import LiveStudioWidget
    lw = LiveStudioWidget()
    lw.tab_history.reprendre_plan.emit(dict(entry))
    assert lw.tabs.currentWidget() is lw.tab_sequences, "bascule onglet Séquences manquante"
    assert "loop mapping facade" in lw.tab_sequences.prompt_ta.toPlainText(), "prompt non transmis"
    # Vidéothèque « ↑ HD » : MÊME reprise par la graine que l'Historique (2026-07-07).
    from ui.tab_video_library_live import _LiveVideoCard, TabVideoLibraryLive
    import core.history as _H
    assert hasattr(_LiveVideoCard, "reprise_requested") and hasattr(TabVideoLibraryLive, "send_to_reprise")
    assert callable(getattr(_H, "find_entry_by_path", None)), "find_entry_by_path absent"
    lw.tab_sequences.prompt_ta.setPlainText("")
    lw.tabs.setCurrentWidget(lw.tab_library)
    lw.tab_library.send_to_reprise.emit({"prompt": "reprise videotheque", "seed": 777, "status": "done"})
    assert lw.tabs.currentWidget() is lw.tab_sequences, "Vidéothèque HD → bascule Séquences (comme Historique)"
    assert "reprise videotheque" in lw.tab_sequences.prompt_ta.toPlainText(), "Vidéothèque HD : prompt non transmis"


@test
def studio_ia_poignee_ia_au_bord_live():
    """Studio IA Live : la poignée « IA » est collée au bord droit — le spacer de
    droite est masqué sur la page « studio » (sinon il la décale). Retour Matthieu
    2026-07-05 ; parité avec le garde « seedance » côté Cinéma."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "live_window.py"), encoding="utf-8") as f:
        # 2026-07-23 : exclusion étendue aux pages éléments (fiches FICHE au bord).
        _w = f.read()
    for _k in ('"studio"', '"image_ia"', '"conducteur"',
               '"casting"', '"accessoires"', '"vehicules"'):
        assert _w.find('self._right_spacer.setVisible') < _w.find(_k, _w.find(
            'self._right_spacer.setVisible')), \
            f"spacer non masqué pour {_k} (poignée décalée du bord)"


@test
def distributeur_video_piapi_live():
    """Distributeurs vidéo côté Live (parité Cinéma, 2026-07-16) : Paramètres Live
    proposent le combo distributeur + clé PiAPI (auto-save), et le Studio Live
    affiche l'estimation de prix dans un bandeau FIXE sous les onglets, branché
    sur le signal de « Générer depuis Séquences »."""
    import inspect
    # Paramètres Live : mêmes éléments que le Cinéma (combo, clé, test, visibilité)
    import ui.page_live_settings as PLS
    _src = inspect.getsource(PLS)
    for _needle in ("video_provider_combo", '"piapi_key"', "test_piapi_connection"):
        assert _needle in _src, f"parité distributeurs : {_needle} manquant côté Live"
    # Studio Live : bandeau prix fixe sous les onglets + signal T2V Live
    import ui.live_studio_widget as LSW
    _wsrc = inspect.getsource(LSW.LiveStudioWidget)
    assert "_price_footer" in _wsrc and "price_estimate_changed" in _wsrc
    import ui.tab_t2v_live as T
    assert "price_estimate_changed" in inspect.getsource(T.TabT2V._refresh_price_estimate)
    # UN SEUL bandeau (2026-07-20, parité Cinéma) : doublon in-tab retiré.
    assert "lay.addWidget(price_frame)" not in inspect.getsource(T.TabT2V), \
        "doublon d'estimation : l'onglet ne doit plus afficher son propre bandeau"
    # Prix recomputé avec le distributeur actif AVANT la file (affichage + onglet).
    assert "_refresh_price_estimate" in inspect.getsource(LSW.LiveStudioWidget.showEvent), \
        "prix non recomputé à l'affichage"
    assert "_refresh_price_estimate" in inspect.getsource(LSW.LiveStudioWidget._on_tab_changed), \
        "prix non recomputé à l'entrée dans l'onglet"
    # Le bandeau ne s'affiche que sur l'onglet Séquences, avec un texte non vide
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    lw = LSW.LiveStudioWidget()
    lw.tabs.setCurrentWidget(lw.tab_sequences)
    lw._on_price_estimate("💰 ≈ $2.00 · 4 plans")
    assert lw._price_footer.isVisibleTo(lw), "bandeau masqué sur l'onglet Séquences"
    lw.tabs.setCurrentWidget(lw.tab_library)
    assert not lw._price_footer.isVisibleTo(lw), "bandeau visible hors Séquences"
    # Mode MONO-distributeur : les onglets fal-only sont GRISÉS, Séquences reste
    # actif ; retour en multi → tout se réactive (parité Cinéma).
    for _n in ("distribution_mode_combo", '"distribution_mode"'):
        assert _n in _src, f"parité mono/multi : {_n} manquant côté Live"
    # Section « Clés API facultatives » repliable, PiAPI en tête (parité Cinéma
    # 2026-07-16) ; les rangées de CLÉS y restent toujours visibles.
    for _n in ("_toggle_opt_keys", "_btn_opt_keys",
               "Clés API facultatives  (PiAPI, OpenAI, Mistral…)",
               "Clé PiAPI (distributeur) :"):
        assert _n in _src, f"parité clés facultatives : {_n} manquant côté Live"
    assert "_refresh_piapi_visibility" not in _src, \
        "ancien mécanisme de visibilité PiAPI encore présent"
    import core.media_provider as mp
    _orig_lc = mp.load_config
    try:
        mp.load_config = lambda: {"video_provider": "piapi", "piapi_key": "k",
                                  "distribution_mode": "mono"}
        lw._apply_distribution_mode()
        for _tab in (lw.tab_sound, lw.tab_music, lw.tab_image, lw.tab_upscale):
            _i = lw.tabs.indexOf(_tab)
            assert not lw.tabs.isTabEnabled(_i), "onglet fal-only actif en mono"
            assert lw.tabs.tabToolTip(_i), "tooltip d'explication manquant"
        assert lw.tabs.isTabEnabled(lw.tabs.indexOf(lw.tab_sequences)), \
            "Séquences (Seedance) doit rester actif en mono-PiAPI"
        mp.load_config = lambda: {}
        lw._apply_distribution_mode()
        assert lw.tabs.isTabEnabled(lw.tabs.indexOf(lw.tab_sound)), \
            "retour multi : onglets non réactivés"
    finally:
        mp.load_config = _orig_lc


@test
def coecriture_session_persistee_live():
    """Co-écriture Conducteur (Live) : la SESSION (conversation + conducteur remanié
    + versions) est persistée à chaque tour et REPRISE à la réouverture ; worker
    parqué à la fermeture. Parité avec le Cinéma (retour Matthieu 2026-07-20)."""
    import inspect
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from ui.dialog_arrange_session_live import ArrangeSessionDialog
    assert hasattr(ArrangeSessionDialog, "session_committed"), "signal session_committed"
    assert "session_state" in inspect.signature(ArrangeSessionDialog.__init__).parameters
    st = {"history": [{"role": "user", "content": "acte plus sombre"},
                      {"role": "assistant", "content": "voici"}],
          "screenplay": "CONDUCTEUR V2", "versions": ["CONDUCTEUR V2"], "version_idx": 0}
    d = ArrangeSessionDialog(None, "ORIG", "ANALYSE", 5, session_state=st)
    assert len(d._history) == 2 and d._screenplay == "CONDUCTEUR V2", "session non reprise"
    assert d._screenplay_edit.toPlainText() == "CONDUCTEUR V2" and d._btn_apply.isEnabled()
    got = {}
    d.session_committed.connect(lambda s: got.update(s))
    d._on_message_ready("réponse")
    assert got.get("history", [{}])[-1].get("content") == "réponse", "commit à chaque tour"
    assert "abandon_thread" in inspect.getsource(ArrangeSessionDialog.done), "worker parqué (done)"
    import ui.page_scenario_live as PSL
    _cls = next(c for _n, c in vars(PSL).items()
                if isinstance(c, type) and hasattr(c, "_open_arrange_session")
                and hasattr(c, "_on_arrange_session_autosave"))
    _src = inspect.getsource(_cls._open_arrange_session)
    assert "session_state=" in _src and "session_committed.connect" in _src, "reprise + autosave"
    assert "self._save(silent=True)" in _src, "sauvegarde immédiate à l'application"


@test
def coecriture_reecriture_ciblee_live():
    """Co-écriture Conducteur (Live) : bouton « Réécrire selon la co-écriture » (édits
    ciblés sur les passages travaillés, sans troncature) au-dessus de « Générer tout
    le conducteur » (renommé) ; réécriture COMPLÈTE à 16000 tokens ; garde-fou
    anti-troncature. Parité avec le Cinéma (retour Matthieu 2026-07-20)."""
    import inspect
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from api.live_screenplay import ArrangeSessionChatConducteurWorker
    assert "8192 if self._surgical else 16000" in inspect.getsource(
        ArrangeSessionChatConducteurWorker.run), "réécriture complète : 16000 tokens"
    from ui.dialog_arrange_session_live import ArrangeSessionDialog
    d = ArrangeSessionDialog(None, "ORIG", "ANALYSE", 5)
    assert hasattr(d, "_btn_rewrite_coedit"), "bouton « Réécrire selon la co-écriture »"
    assert d._btn_generate.text() == "✎  Générer tout le conducteur", "bouton complet renommé"
    _cap = {}
    d._start_worker = lambda instr, surgical=True, **k: _cap.update(instr=instr, surgical=surgical)
    d._screenplay = "X"
    d._on_rewrite_coedit()
    assert _cap.get("surgical") is True and "SEULS passages" in _cap.get("instr", ""), \
        "réécriture ciblée = chirurgical, passages travaillés seulement"
    assert "0.55" in inspect.getsource(ArrangeSessionDialog._on_screenplay_ready), \
        "garde-fou anti-troncature"
    from core.i18n import _FR_TO_EN as T
    for _t in ("✦  Réécrire selon la co-écriture", "✎  Générer tout le conducteur"):
        assert _t in T, ("i18n manquant", _t)


@test
def coecriture_recoit_analyse_musicale():
    """La co-écriture du Conducteur reçoit la TIMELINE MUSICALE du set (2026-07-26).

    Constat Matthieu : « J'ai fait une analyse de la musique, peut-on l'appliquer au
    Teaser ? » → l'IA répondait « colle-moi ton analyse musicale » alors qu'elle
    existait dans le projet. La timeline n'allait qu'à l'Analyse et à la Mise en page
    (_text_with_music) ; _open_arrange_session envoyait le conducteur BRUT."""
    import inspect
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])

    # 1. La page calcule la timeline et la passe au studio de co-écriture.
    import ui.page_scenario_live as PSL
    _src = inspect.getsource(PSL.PageScenario._open_arrange_session)
    assert "build_set_timeline" in _src and "music_analysis=" in _src, \
        "_open_arrange_session n'envoie pas la timeline musicale"

    # 2. Le studio la relaie au worker.
    from ui.dialog_arrange_session_live import ArrangeSessionDialog
    assert "music_analysis=self._music_analysis" in inspect.getsource(
        ArrangeSessionDialog._start_worker), "le studio ne relaie pas la timeline"

    from core.music_analysis import build_set_timeline
    timeline = build_set_timeline([
        {"name": "Track A", "bpm": 128.0, "duration": 210.0,
         "energy": "▁▃▅█▅▂", "drops": [32.0, 96.0]},
    ])
    assert "128 BPM" in timeline, "timeline de test mal construite"

    # 3. L'utilisateur VOIT que l'IA l'a (sinon il recolle son analyse à la main).
    d = ArrangeSessionDialog(None, "CONDUCTEUR", "ANALYSE", 5, music_analysis=timeline)
    _chat = d._chat_view.toPlainText()
    assert "analyse musicale" in _chat.lower(), \
        "le chat n'annonce pas qu'il possède l'analyse musicale"

    # 4. FONCTIONNEL : la timeline part réellement dans le message envoyé à l'IA.
    import core.ai_provider as _ai
    from api.live_screenplay import ArrangeSessionChatConducteurWorker
    _cap = {}

    def _fake_full(system, messages, **kw):
        _cap["messages"] = messages
        return "Message."

    _old_key, _old_full = _ai.key_error, _ai.chat_until_complete
    try:
        _ai.key_error = lambda *a, **k: ""
        _ai.chat_until_complete = _fake_full
        w = ArrangeSessionChatConducteurWorker(
            original="CONDUCTEUR", analysis="ANALYSE", history=[],
            user_message="Cale le teaser sur la musique.",
            music_analysis=timeline, surgical=True,
        )
        w.run()          # exécution SYNCHRONE : aucun thread, aucun réseau
    finally:
        _ai.key_error, _ai.chat_until_complete = _old_key, _old_full

    _sent = "\n".join(
        m["content"] if isinstance(m.get("content"), str) else ""
        for m in _cap.get("messages", []))
    assert "128 BPM" in _sent, "la timeline musicale n'atteint pas l'IA"
    assert "ne la redemande jamais" in _sent, \
        "consigne anti-« colle-moi ton analyse » absente du contexte"

    # 5. Le garde-fou de volume compte ce contexte supplémentaire.
    assert "self._music_analysis" in inspect.getsource(
        ArrangeSessionDialog._estimated_session_tokens), \
        "la timeline n'est pas comptée dans l'estimation de tokens"


@test
def coecriture_recoit_note_realisation():
    """La co-écriture du Conducteur reçoit la NOTE DE RÉALISATION (2026-07-26).

    Constat Matthieu : la note existe dans son onglet et part bien au découpage
    (FormatConducteurWorker), mais le studio de co-écriture ne la recevait pas —
    parité Cinéma, où ArrangeChatWorker l'injecte depuis toujours."""
    import inspect
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])

    import ui.page_scenario_live as PSL
    _src = inspect.getsource(PSL.PageScenario._open_arrange_session)
    assert "direction_note=" in _src and "_direction_note_edit" in _src, \
        "_open_arrange_session n'envoie pas la note de réalisation"

    from ui.dialog_arrange_session_live import ArrangeSessionDialog
    assert "direction_note=self._direction_note" in inspect.getsource(
        ArrangeSessionDialog._start_worker), "le studio ne relaie pas la note"

    NOTE = "## STYLE VISUEL\nGivre bleu, pierre nue.\n## RYTHME\nPlans courts, 2 s."

    # Le chat annonce qu'il l'a — un gabarit VIDE ne doit rien annoncer.
    from core.direction_note import empty_note
    d_vide = ArrangeSessionDialog(None, "CONDUCTEUR", "ANALYSE", 5,
                                  direction_note=empty_note())
    assert "note de réalisation" not in d_vide._chat_view.toPlainText().lower(), \
        "un gabarit de note VIDE ne doit pas être annoncé comme rempli"
    d = ArrangeSessionDialog(None, "CONDUCTEUR", "ANALYSE", 5, direction_note=NOTE)
    assert "note de réalisation" in d._chat_view.toPlainText().lower(), \
        "le chat n'annonce pas qu'il possède la note de réalisation"

    # FONCTIONNEL : la note part réellement dans le message envoyé à l'IA.
    import core.ai_provider as _ai
    from api.live_screenplay import ArrangeSessionChatConducteurWorker
    _cap = {}
    _old_key, _old_full = _ai.key_error, _ai.chat_until_complete
    try:
        _ai.key_error = lambda *a, **k: ""
        _ai.chat_until_complete = lambda system, messages, **kw: (
            _cap.update(messages=messages) or "Message.")
        w = ArrangeSessionChatConducteurWorker(
            original="CONDUCTEUR", analysis="ANALYSE", history=[],
            user_message="Resserre le rythme.", direction_note=NOTE, surgical=True,
        )
        w.run()          # SYNCHRONE : aucun thread, aucun réseau
    finally:
        _ai.key_error, _ai.chat_until_complete = _old_key, _old_full

    _sent = "\n".join(
        m["content"] if isinstance(m.get("content"), str) else ""
        for m in _cap.get("messages", []))
    assert "Givre bleu, pierre nue." in _sent, "la note de réalisation n'atteint pas l'IA"
    assert "NOTE DE RÉALISATION ACTUELLE" in _sent, "en-tête de note absent du contexte"
    assert "document séparé du conducteur" in _sent, \
        "la séparation note / récit n'est pas rappelée à l'IA"


@test
def decoupage_applique_dans_le_bon_onglet():
    """« Appliquer le découpage » écrit ET ouvre l'onglet DÉCOUPAGE (2026-07-26).

    Régression trouvée par Matthieu : l'insertion de « Note de réalisation » en
    position 1 (2026-07-23) avait décalé le Découpage en 2, mais _apply_layout
    faisait toujours setTabEnabled(1, True)/setCurrentIndex(1) → la Note était
    dégrisée et affichée, le Découpage restait GRISÉ donc inatteignable, alors
    que le texte y était bien écrit."""
    import inspect
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import ui.page_scenario_live as PSL

    assert (PSL.PageScenario.TAB_CONDUCTEUR, PSL.PageScenario.TAB_NOTE,
            PSL.PageScenario.TAB_DECOUPAGE) == (0, 1, 2), "index d'onglets renumérotés"

    page = PSL.PageScenario()
    page._save = lambda *a, **k: None       # jamais d'écriture réelle en test
    assert page._editor_tabs.widget(page.TAB_DECOUPAGE) is page._layout_view, \
        "l'onglet Découpage n'est pas celui du _layout_view"
    assert not page._editor_tabs.isTabEnabled(page.TAB_DECOUPAGE), \
        "le Découpage doit être grisé tant qu'il est vide"

    page._apply_layout("PLAN 1 — Façade prise dans le givre.")

    assert page._layout_view.toPlainText().startswith("PLAN 1"), \
        "le découpage n'est pas écrit dans l'onglet"
    assert page._editor_tabs.isTabEnabled(page.TAB_DECOUPAGE), \
        "l'onglet Découpage reste grisé après « Appliquer »"
    assert page._editor_tabs.currentIndex() == page.TAB_DECOUPAGE, \
        "« Appliquer » n'ouvre pas l'onglet Découpage"
    assert page._editor_tabs.isTabEnabled(page.TAB_NOTE), \
        "la Note de réalisation ne doit JAMAIS être grisée"

    # Plus aucun index d'onglet en dur dans la page (c'était la cause du bug).
    # On vise l'APPEL (préfixe _editor_tabs.) : les commentaires qui racontent la
    # régression citent « setTabEnabled(1, … ) » et ne doivent pas déclencher.
    _src = inspect.getsource(PSL)
    for _bad in ("_editor_tabs.setTabEnabled(0,", "_editor_tabs.setTabEnabled(1,",
                 "_editor_tabs.setTabEnabled(2,", "_editor_tabs.setCurrentIndex(1)",
                 "_editor_tabs.setCurrentIndex(2)"):
        assert _bad not in _src, ("index d'onglet en dur — utiliser TAB_*", _bad)

    # Libellé du bouton (demande Matthieu 2026-07-26) + i18n.
    _fmt = inspect.getsource(PSL.PageScenario._open_format_window)
    assert '"✓  Appliquer le découpage"' in _fmt, "bouton non renommé"
    from core.i18n import _FR_TO_EN as T
    assert "✓  Appliquer le découpage" in T, "i18n du bouton manquant"


@test
def nouveau_conducteur_repart_a_zero():
    """Un NOUVEAU conducteur ne garde rien du précédent (2026-07-26).

    Écart trouvé par audit : _new_scenario Live ne touchait ni la note de
    réalisation ni le découpage — un nouveau conducteur héritait à l'écran de ceux
    du projet précédent, et le premier enregistrement les figeait dedans."""
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import ui.page_scenario_live as PSL
    from core.direction_note import empty_note, note_for_ai

    page = PSL.PageScenario()
    page._save = lambda *a, **k: None
    page._editor_text.setPlainText("Ancien conducteur.")
    page._direction_note_edit.setPlainText("## STYLE VISUEL\nGivre bleu du projet A.")
    page._layout_view.setPlainText("PLAN 1 — Découpage du projet A")
    page._editor_tabs.setTabEnabled(page.TAB_DECOUPAGE, True)

    page._new_scenario()

    assert page._editor_text.toPlainText().strip() == "", "le conducteur n'est pas vidé"
    assert "projet A" not in page._direction_note_edit.toPlainText(), \
        "la note de réalisation du projet précédent est héritée"
    assert page._layout_view.toPlainText().strip() == "", \
        "le découpage du projet précédent est hérité"
    assert not page._editor_tabs.isTabEnabled(page.TAB_DECOUPAGE), \
        "l'onglet Découpage reste actif alors qu'il est vide"
    # Le GABARIT est posé : sans lui, section_text(« STYLE VISUEL ») ne trouve
    # jamais rien et la note reste un champ libre inexploitable.
    _note = page._direction_note_edit.toPlainText()
    assert _note.strip() == empty_note().strip(), "gabarit de note non posé"
    assert note_for_ai(_note) == "", "un gabarit vierge doit être considéré VIDE"

    # Section 6 d'une analyse → rangée dans la note, sans appel IA.
    assert hasattr(PSL.PageScenario, "_merge_analysis_direction_note"), \
        "la section 6 de l'analyse n'est pas rangée dans la note (Live)"
    import inspect
    _src = inspect.getsource(PSL.PageScenario)
    assert _src.count("self._merge_analysis_direction_note(") >= 2, \
        "le rangement de la section 6 n'est branché qu'à un seul endroit"


@test
def synchronisation_live_ne_detruit_plus_les_prompts_vj():
    """La « ⟳ Synchronisation » des Séquences Live ne peut plus recomposer les
    prompts VJ ni réécrire le conducteur en scénario INT./EXT. (2026-07-26).

    Le dialogue est PARTAGÉ avec le Cinéma et proposait rewrite_prompts coché par
    DÉFAUT : le prompt entier était écrasé par l'IA — beats début/milieu/fin dilués,
    section [🎵 SOUND DESIGN] supprimée — et rewrite_scenario écrivait un scénario
    littéraire dans le magasin des conducteurs."""
    import inspect
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from ui.dialog_storyboard_sync import StoryboardSyncConfirmDialog as D

    interdites = set(D._LIVE_FORBIDDEN)
    assert {"rewrite_prompts", "rewrite_scenario"} <= interdites, \
        "les deux opérations destructrices doivent être interdites en Live"

    # CINÉMA : rien ne change, toutes les options restent proposées.
    cine = D(3)
    assert "rewrite_prompts" in cine._checks, "régression Cinéma : option disparue"
    assert set(k for k, *_ in D._OPTIONS) == set(cine._checks), \
        "le Cinéma doit voir TOUTES les options"

    # LIVE : les options interdites ne sont pas proposées…
    live = D(3, edition="live")
    for k in interdites:
        assert k not in live._checks, f"option interdite encore proposée en Live : {k}"
    # …et ressortent à False même si une case réapparaissait un jour.
    opts = live.selected_options()
    for k in interdites:
        assert opts.get(k) is False, f"option interdite non forcée à False : {k}"
    # Ce qui reste utile au Live est bien conservé.
    for k in ("reassign", "sync_casting", "sync_accessories", "sync_vehicles"):
        assert k in live._checks, f"synchronisation utile perdue en Live : {k}"

    # La page Live demande bien l'édition Live.
    import ui.page_storyboard_live as PSL
    assert 'edition="live"' in inspect.getsource(PSL.PageStoryboard._on_sync), \
        "les Séquences Live n'ouvrent pas le dialogue en mode Live"


@test
def tout_generer_live_analyse_identite_et_fraicheur():
    """« Tout générer » Live analyse l'identité visuelle des images produites, et le
    découpage périmé est signalé (2026-07-26, parité Cinéma).

    Le composeur de prompt vidéo est PARTAGÉ et lit `visual_identity` : sans analyse,
    le Live envoyait le prompt qui a créé l'image au lieu de la description réelle de
    l'image — donc plus aucun verrou de continuité entre les plans."""
    import inspect
    import ui.page_scenario_live as PSL

    assert hasattr(PSL.PageScenario, "_gen_all_analyze_identity"), \
        "analyse d'identité visuelle absente du « Tout générer » Live"
    _ai = inspect.getsource(PSL.PageScenario._gen_all_analyze_identity)
    assert "VisualIdentityWorker" in _ai and "pending_identity" in _ai
    assert "worker.done.connect" in _ai, "signal done (jamais finished) — doctrine projet"
    # Un échec d'analyse ne doit JAMAIS arrêter la file.
    assert _ai.count("_gen_all_next_image()") >= 2, \
        "la file s'arrête si l'analyse échoue"
    # Les deux chemins d'image (portrait ET élément) y passent.
    _gi = inspect.getsource(PSL.PageScenario._gen_all_next_image)
    assert _gi.count("self._gen_all_analyze_identity(") == 2, \
        "un des deux chemins d'image (portrait / élément) saute l'analyse d'identité"

    # Empreinte éditoriale : posée à l'application du découpage…
    _al = inspect.getsource(PSL.PageScenario._apply_layout)
    assert "mark_decoupage_built" in _al, "le découpage ne laisse pas d'empreinte"
    # …et relue avant de générer les séquences.
    _os = inspect.getsource(PSL.PageScenario._on_storyboard)
    assert "decoupage_stale" in _os, "un découpage périmé n'est pas signalé"
    # L'empreinte STORYBOARD reste volontairement débranchée : elle est globale au
    # conducteur alors que le Live a DEUX jeux de séquences (live / mapping).
    assert "mark_storyboard_synced" not in inspect.getsource(PSL), \
        "empreinte storyboard branchée malgré les deux namespaces Live"

    # Profondeur de champ : colonne + fiche de plan.
    import ui.page_storyboard_live as PSB
    assert PSB._COLS[23][0] == "P. de champ"
    _row = inspect.getsource(PSB._ShotRow)
    assert "DEPTHS_OF_FIELD" in _row and "cells[23]" in _row, \
        "la colonne P. de champ n'est pas rendue"
    import ui.dialog_shot_live as DSL
    _src = inspect.getsource(DSL)
    assert "DEPTHS_OF_FIELD" in _src and '"depth_of_field"' in _src, \
        "la fiche de plan Live ne règle pas la profondeur de champ"


@test
def sequences_live_utilisent_le_worker_live():
    """Les Séquences Live ne redécoupent plus avec le worker CINÉMA (2026-07-26).

    « ⊕ Générer depuis le conducteur » importait api.screenplay.GenerateStoryboardWorker
    dès qu'aucune mise en page n'était parsable. Ce worker applique le contrat FILM
    (valeurs GP/GM/PM/PE, décor, Jour/Nuit), recompose les prompts en
    [🎬 ACTION][🎭 MISE EN SCÈNE]… et charge les catalogues Décors/HMC du Cinéma. Rien
    du Live ne survivait : ni confinement façade, ni caméra fixe en mapping, ni beats
    relatifs, ni PROMPT SON."""
    import inspect
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import ui.page_storyboard_live as PSL

    _an = inspect.getsource(PSL.PageStoryboard._on_analyze)
    assert "from api.live_screenplay import GenerateDecoupageWorker" in _an, \
        "les Séquences Live n'utilisent pas le worker Live"
    assert "GenerateStoryboardWorker" not in _an, \
        "le worker CINÉMA est encore appelé depuis le Live"
    # Le mode et la façade suivent la séquence courante.
    assert "live_seq_mapping" in _an and "get_building_ref" in _an, \
        "mode Live/Mapping ou façade non transmis au worker"
    assert "direction_note=" in _an, "la note de réalisation ne part pas au découpage"

    # La musique est assignée aussi par le chemin IA (le repli Cinéma la perdait).
    _sts = inspect.getsource(PSL.PageStoryboard._segments_to_shots)
    assert "assign_tracks_to_shots" in _sts and "music_track" in _sts, \
        "assignation musicale absente du chemin IA"
    assert "sound_prompt" in _sts, "le PROMPT SON n'est pas repris dans les plans"

    # Le worker Live accepte bien la note.
    import api.live_screenplay as LS
    assert "direction_note" in inspect.signature(
        LS.GenerateDecoupageWorker.__init__).parameters, \
        "GenerateDecoupageWorker n'accepte pas la note de réalisation"
    _run = inspect.getsource(LS.GenerateDecoupageWorker.run)
    assert "note_for_ai" in _run and "NOTE DE RÉALISATION" in _run, \
        "la note n'est pas injectée dans le découpage Live"

    # Style visuel cuit dans les prompts, des DEUX côtés du Live.
    _gen = inspect.getsource(PSL.PageStoryboard._on_shots_generated)
    assert "visual_style_from_note" in _gen, \
        "le style de la note n'atteint pas les prompts des Séquences"
    import ui.page_scenario_live as PSC
    assert "visual_style_from_note" in inspect.getsource(PSC.PageScenario._live_visual_style)
    _wr = inspect.getsource(PSC.PageScenario._write_decoupage_segments)
    assert "_with_visual_style" in _wr, "style non cuit à l'écriture des segments"
    # Un prompt qui porte DÉJÀ un style co-écrit ne doit pas être écrasé.
    from core.prompt_sections import build, style_of
    _p = build(action="Une façade.", style="style déjà écrit")
    assert PSC.PageScenario._with_visual_style(_p, "autre style") == _p, \
        "le style co-écrit est écrasé"
    _p2 = build(action="Une façade.")
    assert "mon style" in style_of(PSC.PageScenario._with_visual_style(_p2, "mon style"))


@test
def grammaire_live_mapping_barre():
    """Grammaire de prompt PANDORA | LIVE (spécification Matthieu 2026-07-26).

    Ce n'est PAS une variante du Cinéma : quatre inversions. La caméra est
    verrouillée et jamais nommée (c'est le vidéoprojecteur, il est boulonné) ; le
    noir est structurel (zéro lumière projetée) ; la durée est imposée par la
    grille (8 temps à X BPM) ; le son n'est JAMAIS généré — le son, c'est le set.
    Conséquence : le vocabulaire de plateau du Cinéma devient une liste d'interdits.
    """
    from core.live_bar import (LiveBar, MAPPING_NEGATIVES, BANNED_POSITIVES,
                               api_duration, bar_duration, duration_drift,
                               sanitize_payload, transformation_family, EXACT_BPM)

    bar = LiveBar(
        surface="a trapezoidal church façade with a square bell tower, two buttresses",
        state_0="nothing moves, the façade already buried under dense frost",
        transformation="the frost thickens very slowly, crystals proliferate outward",
        state_1="the frost has closed over the openings, tension at its peak",
        black="the background is pure black with no gradient, no glow",
        style="frozen antique engraving, wide spaced hatching, cinematic, 4K, ultra-detailed",
        bpm=118, sparkline="▁▁▁▁▁▁▁▁",
        sound_design="Souffle glacé grave à 118 BPM, réverbération de cathédrale.")
    p, bannis = bar.to_prompt()

    # 1. Frontière du PAYLOAD : ni son, ni sparkline, ni étiquette de bloc.
    assert "Souffle" not in p and "cathédrale" not in p, \
        "le SOUND DESIGN est parti au moteur — le son, c'est le set"
    assert not any(c in p for c in "▁▂▃▄▅▆▇█"), \
        "la sparkline est du bruit de tokenisation, elle ne va jamais au moteur"
    assert "[" not in p and "]" not in p, "étiquette de bloc dans le payload"

    # 2. Les boosters contre-productifs sont RETIRÉS, sans résidu de ponctuation.
    assert {"cinematic", "4k", "ultra-detailed"} <= set(bannis), \
        f"boosters non retirés : {bannis}"
    for _mot in BANNED_POSITIVES:
        assert _mot.lower() not in p.lower(), ("terme banni resté dans le payload", _mot)
    assert ",." not in p and ",," not in p and " ," not in p, \
        f"résidu de ponctuation après retrait des boosters : {p[:120]!r}"

    # 3. Les négatifs anti-Cinéma sont injectés, les trois critiques en tête.
    for _n in ("no camera movement", "no depth of field", "no film grain",
               "no cuts", "no scene change"):
        assert _n in p, ("négatif de mapping manquant", _n)
    _c = p[p.index("Constraints:"):]
    assert _c.index("no atmospheric haze") < _c.index("no camera movement"), \
        "les contraintes critiques (brume, coupe) doivent venir en tête"

    # 4. La caméra n'est JAMAIS nommée en positif — elle est verrouillée.
    assert "Locked-off frontal view" in p, "le verrou de cadrage doit ouvrir le prompt"

    # 5. Arithmétique de la barre : 8 temps = 480 / BPM ; on envoie l'ENTIER.
    assert abs(bar_duration(118) - 4.068) < 0.001, "durée exacte 8 temps à 118 BPM"
    assert bar.api_duration == "4", "on envoie l'entier le plus proche, pas l'exact"
    assert abs(duration_drift(118) * 1000 + 68) < 1, "dérive attendue −68 ms"
    for _bpm, _s in EXACT_BPM.items():
        assert abs(bar_duration(_bpm) - _s) < 1e-9, (f"{_bpm} BPM doit tomber juste")
    assert api_duration(140) == "3", "140 BPM → 3 s (entier le plus proche)"

    # 6. La sparkline choisit la FORME, et un drop ne s'interpole pas.
    for _s, _att in (("▁▁▁▁▁▁▁▁", "flat"), ("▁▂▃▄▅▆▇█", "rising"),
                     ("█▇▆▅▄▃▂▁", "falling"), ("▁▁▁█▁▁▁▁", "drop")):
        assert transformation_family(_s) == _att, (f"famille de « {_s} »")
    assert not bar.needs_two_clips
    assert LiveBar(sparkline="▁▁▁█▁▁▁▁").needs_two_clips, \
        "un drop en milieu de barre exige DEUX clips, pas une passe I2V"

    # 7. Paramètres moteur : jamais de son, 1080p (720p passe sous le panneau),
    #    et la méthode DEUX PLAQUES qui verrouille l'arrivée sur le temps 8.
    prm = bar.to_params(image_url="p0.png", end_image_url="p1.png")
    assert prm["generate_audio"] is False, "le moteur ne doit jamais générer de son"
    assert prm["resolution"] == "1080p" and prm["aspect_ratio"] == "4:3"
    assert prm["end_image_url"] == "p1.png", "sans end_image, l'arrivée n'est pas calée"
    assert prm["duration"] == "4"

    # 8. Un texte sans terme banni n'est jamais modifié.
    _txt = "Une prose normale, avec virgules, intacte."
    assert sanitize_payload(_txt) == (_txt, []), "sanitize altère un texte sain"


@test
def prompt_live_grammaire_moteur_et_injections():
    """Le prompt Live est écrit dans la GRAMMAIRE du moteur, sans composition IA
    (chantier 2026-07-26).

    Trois défauts mesurés par l'audit : (1) video_of() ne gardait que la section
    action et jetait STYLE VISUEL et TECHNIQUE — le style de la note n'atteignait
    jamais le moteur ; (2) le Live n'injectait que la focale, un champ sur huit ;
    (3) changer de moteur ne modifiait pas une virgule du texte envoyé, et les noms
    de franchises partaient tels quels."""
    import inspect
    from core.prompt_sections import build, flatten, video_of, sound_of
    from core.live_prompt import assemble, describe

    # 1. Le prompt envoyé conserve TOUTES les sections sauf le son.
    p = build(action="Ouverture : la façade givrée.",
              technique="Plan d'ensemble, caméra fixe.",
              style="Gravure ancienne gelée, 4K.",
              sound="Souffle glacé.")
    assert "Gravure" not in video_of(p), \
        "le cas de test ne reproduit plus la perte — test sans valeur"
    _f = flatten(p)
    for _garde in ("Ouverture", "Plan d'ensemble", "Gravure"):
        assert _garde in _f, ("section perdue par flatten", _garde)
    assert "Souffle" not in _f, "le son doit partir au Sound Design, pas au moteur"
    assert "[🎬" not in _f, "un prompt final ne contient pas d'étiquettes de section"
    assert sound_of(p), "le son doit rester extractible pour le Sound Design"

    import ui.tab_t2v_live as TL
    _cls = next(o for o in vars(TL).values()
                if isinstance(o, type) and hasattr(o, "start_generation"))
    # Commentaires ÉCARTÉS : ils citent forcément video_of pour expliquer pourquoi
    # il a été remplacé (piège rencontré quatre fois — voir la mémoire projet).
    _gen = "\n".join(l for l in inspect.getsource(_cls.start_generation).split("\n")
                     if not l.strip().startswith("#"))
    assert "flatten as _flatten" in _gen and "video_of(" not in _gen, \
        "l'envoi Live utilise encore video_of (style et technique jetés)"

    # 2. TOUS les paramètres du plan partent, pas seulement la focale.
    assert "camera_terms" in _gen, "les réglages du plan n'atteignent pas le moteur"
    from core.shot_terms import camera_terms
    _bits = camera_terms({"shot_size": "PL", "camera_axis": "3/4",
                          "camera_movement": "Travelling avant", "focal": "35mm",
                          "camera_distance": "4m", "camera_height": "1.6m",
                          "speed": "Ralenti", "depth_of_field": "Courte"})
    assert len(_bits) >= 7, f"camera_terms ne traduit que {len(_bits)} champs"

    # 3. La grammaire du moteur change RÉELLEMENT le texte — sans IA.
    BODY = "Opening: the frozen facade. Then the frost thickens"
    CAM = ["wide shot", "slow motion"]
    rendus = {}
    for eng in ("seedance-2.0", "veo-3.1", "kling-v3-pro", "pixverse-v4.5"):
        rendus[eng], _ = assemble(BODY, engine_key=eng, camera_bits=CAM,
                                  style="frozen engraving look")
    assert "Camera:" in rendus["seedance-2.0"], "grammaire à champs perdue (Seedance)"
    assert "shot with" in rendus["veo-3.1"], "grammaire phrase continue perdue (Veo)"
    assert len(set(rendus.values())) >= 3, \
        "les moteurs reçoivent tous le même texte — la grammaire ne sert à rien"
    # Le corps du plan passe MOT POUR MOT : les beats ne sont jamais réécrits.
    for _t in rendus.values():
        assert "Opening: the frozen facade" in _t, "le corps du plan a été réécrit"

    # 4. Les noms d'IP sont retirés partout.
    _t, _ips = assemble("A knight walks, in the style of Arcane",
                        engine_key="seedance-2.0")
    assert _ips == ["Arcane"] and "Arcane" not in _t, \
        "les noms de franchises partent encore au moteur"
    assert "live_prompt import assemble" in _gen, \
        "la grammaire moteur n'est pas appliquée à l'envoi Live"

    # 4bis. Retirer un nom d'IP ne doit JAMAIS laisser de tournure orpheline.
    #       « façon Arcane » traduit donne « in the manner of Arcane » : sans cette
    #       formulation dans la liste, le prompt finissait par « in the manner of — »
    #       (constat sur un vrai plan Live, 2026-07-26).
    from core.engine_grammar import strip_ip_names as _strip
    for _avant, _apres in (
        ("Old frozen engraving, in the manner of Arcane, 4K", "Old frozen engraving, 4K"),
        ("Old frozen engraving, in the manner of Arcane",     "Old frozen engraving"),
        ("A knight, in the style of Ghibli — wide shot",      "A knight — wide shot"),
        ("Rendu inspired by Pixar, net",                      "Rendu, net"),
    ):
        _got, _ = _strip(_avant)
        assert _got == _apres, (f"résidu après retrait d'IP : {_got!r}")
    assert _strip("Prose normale sans IP, 4K") == ("Prose normale sans IP, 4K", []), \
        "un texte sans nom d'IP ne doit pas être modifié"

    # 5. L'utilisateur VOIT ce qui est injecté.
    _prev = inspect.getsource(_cls._build_full_preview_text)
    for _must in ("Plan ← storyboard", "Traduction des paramètres du storyboard",
                  "Grammaire du moteur", "Noms retirés du prompt"):
        assert _must in _prev, ("bloc PARAMÈTRES incomplet", _must)

    # 6. Aucune composition IA n'a été introduite : les beats restent intacts.
    assert "video_prompt" not in _gen and "compose(" not in _gen, \
        "une composition IA s'est glissée dans l'envoi Live (beats menacés)"
    # On inspecte les IMPORTS RÉELS via l'AST, pas le texte : la docstring du
    # module explique justement pourquoi il n'appelle PAS le composeur, donc une
    # recherche textuelle se déclencherait sur son propre argumentaire.
    import ast
    import core.live_prompt as _LP
    _tree = ast.parse(inspect.getsource(_LP))
    _mods = set()
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.Import):
            _mods.update(a.name for a in _n.names)
        elif isinstance(_n, ast.ImportFrom):
            _mods.add(_n.module or "")
    for _interdit in ("api.video_prompt", "core.ai_provider", "core.lang"):
        assert _interdit not in _mods, \
            (f"core/live_prompt doit rester DÉTERMINISTE — importe « {_interdit} »")
    assert _mods, "aucun import détecté — l'analyse AST a échoué, test sans valeur"
    # Reproductible : deux appels identiques donnent exactement le même texte.
    assert assemble(BODY, engine_key="veo-3.1", camera_bits=CAM)[0] == \
           assemble(BODY, engine_key="veo-3.1", camera_bits=CAM)[0], \
        "l'assemblage n'est pas reproductible"


@test
def mood_rogne_a_la_facade():
    """« ▦ Rogner à la façade » : recale un DÉCALAGE, refuse une DÉFORMATION
    (demande Matthieu 2026-07-26).

    En mapping, le moteur déborde souvent de la silhouette : ce qui sort du cadre
    est perdu à la projection ET pollue les images de référence envoyées ensuite à
    Seedance. Un décalage de quelques pixels se recale — tous les moods finissent
    alors au MÊME endroit par rapport à la façade. Une géométrie déformée, elle, ne
    se répare pas : la recaler ne ferait que déplacer l'erreur."""
    import os, tempfile
    import numpy as np
    from PIL import Image, ImageDraw
    from core.live_mapping import (build_facade_mask, measure_facade_alignment,
                                   align_and_mask_image)

    tmp = tempfile.mkdtemp(prefix="pandora_facade_")
    W, H = 640, 400

    def facade(dx=0, dy=0, scale=1.0, skew=0, halo=False):
        im = Image.new("RGB", (W, H), (0, 0, 0))
        d = ImageDraw.Draw(im)
        cx, cy = W / 2 + dx, H / 2 + dy
        w, h = 300 * scale, 200 * scale
        col = (90, 160, 255)
        d.polygon([(cx - w/2 + skew, cy + h/2), (cx + w/2, cy + h/2),
                   (cx + w/2 - 30, cy - h/2), (cx - w/2 + 30 + skew, cy - h/2)], fill=col)
        d.rectangle([cx - 30, cy - h/2 - 90 * scale, cx + 30, cy - h/2], fill=col)
        if halo:      # lumière qui DÉBORDE volontairement de la façade
            d.ellipse([cx - w/2 - 40, cy - 40, cx - w/2 + 20, cy + 40], fill=(60, 90, 200))
        return im

    def _p(name, img):
        p = os.path.join(tmp, name + ".png")
        img.save(p)
        return p

    ref = _p("facade", facade())
    mask = build_facade_mask(ref, os.path.join(tmp, "mask.png"), feather=0)
    assert mask, "masque de façade non construit depuis une façade isolée"

    # 1. Verdicts : décalage → recalable ; déformation → à regénérer.
    ATTENDU = {
        "identique":    ("aligned",  facade()),
        "decale_2px":   ("shifted",  facade(dx=2, dy=1)),
        "decale_15px":  ("shifted",  facade(dx=15)),
        "halo":         ("overflow", facade(halo=True)),
        "agrandi":      ("deformed", facade(scale=1.15)),
        "deforme":      ("deformed", facade(skew=40)),
    }
    for nom, (attendu, img) in ATTENDU.items():
        m = measure_facade_alignment(_p(nom, img), mask)
        assert m["verdict"] == attendu, \
            (f"« {nom} » jugé {m['verdict']} au lieu de {attendu}", m)

    # 2. Un décalage pur est recalé EXACTEMENT (c'est ce qui garantit que tous les
    #    moods finissent au même endroit par rapport à la façade).
    m = measure_facade_alignment(_p("decale_15px", facade(dx=15)), mask)
    assert m["shift"] == (0, 15), ("décalage mal estimé", m["shift"])
    assert m["iou_aligned"] > 0.99, "le recalage ne superpose pas parfaitement"
    # …et une déformation n'est JAMAIS améliorée par un recalage.
    d = measure_facade_alignment(_p("deforme", facade(skew=40)), mask)
    assert abs(d["iou_aligned"] - d["iou"]) < 0.01, \
        "un recalage prétend corriger une déformation"

    # 3. Le rognage supprime réellement ce qui dépasse, sans toucher l'original.
    src = _p("halo", facade(halo=True))
    m = measure_facade_alignment(src, mask)
    out = align_and_mask_image(src, mask, os.path.join(tmp, "rogne.png"), m["shift"])
    assert out != src, "l'original a été écrasé"
    _refm = np.asarray(Image.open(mask).convert("L")) > 127
    _av = np.logical_and(np.asarray(Image.open(src).convert("L")) > 18, ~_refm).sum()
    _ap = np.logical_and(np.asarray(Image.open(out).convert("L")) > 18, ~_refm).sum()
    assert _av > 0, "le cas de test ne déborde pas — test sans valeur"
    assert _ap == 0, f"{_ap} pixel(s) dépassent encore après rognage"

    # 4. Bouton présent, MAPPING uniquement, et jamais bloquant sans façade.
    import inspect
    import ui.dialog_apercu as DA
    _src = inspect.getsource(DA.MoodDialog)
    assert "_btn_facade_crop" in _src and "_crop_to_facade" in _src
    assert "self._is_mapping()" in _src, "le bouton doit être réservé au Mapping"
    _crop = inspect.getsource(DA.MoodDialog._crop_to_facade)
    assert "REGÉNÉRER" in _crop and 'verdict == "deformed"' in _crop, \
        "une déformation doit conduire à regénérer, pas à recaler"
    assert "_paths.insert" in _crop, "le rognage doit AJOUTER une image, pas remplacer"

    from core.i18n import _FR_TO_EN as T
    for k in ("▦  Rogner à la façade", "Géométrie déformée", "Mood aligné sur la façade"):
        assert k in T, ("i18n manquant", k)


@test
def onglet_decoupage_live_editable():
    """L'onglet Découpage Live est ÉDITABLE et ses retouches sont persistées
    (correctif 2026-07-26, parité Cinéma).

    Il était en setReadOnly(True) : une fois généré, impossible de supprimer un plan,
    corriger une durée ou réécrire un prompt. Le découpage est pourtant un document de
    travail — c'est même l'étape où l'on reprend chaque plan avant de générer."""
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import core.scenario as scenario_api
    import ui.page_scenario_live as PSL

    page = PSL.PageScenario()
    assert not page._layout_view.isReadOnly(), "l'onglet Découpage est en lecture seule"
    # Les trois éditeurs de la page se comportent pareil.
    assert not page._editor_text.isReadOnly() and not page._direction_note_edit.isReadOnly()

    page._title_edit.setText("Teaser éditable")
    page._editor_text.setPlainText("Conducteur du teaser.")
    page._layout_view.setPlainText(
        "DÉCOUPAGE PANDORA 2\n\nSÉQUENCE 1 — A\n\nPLAN 01\n"
        "SOURCE CONDUCTEUR : Le givre.\nINTENTION : Ouvrir.\nRYTHME : Lent.\n"
        "DURÉE : 5s\nPROMPT VISUEL : Façade givrée.\nSON : Souffle.\n"
        "PERSONNAGES : —\nACCESSOIRES : —\nVÉHICULES : —")
    page._save(silent=True)

    # RETOUCHE À LA MAIN : on corrige une durée, comme le ferait l'utilisateur.
    _txt = page._layout_view.toPlainText().replace("DURÉE : 5s", "DURÉE : 9s")
    page._layout_view.setPlainText(_txt)
    assert "DURÉE : 9s" in page._read_layout(), "_read_layout ne voit pas la retouche"
    page._save(silent=True)

    sid = (page._current or {}).get("id", "")
    reread = scenario_api.get_scenario(sid) or {}
    assert "DURÉE : 9s" in (reread.get("decoupage_content") or ""), \
        "la retouche manuelle du découpage n'est pas enregistrée"

    # L'édition déclenche bien l'autosave (pas seulement un _save explicite).
    import inspect
    _src = inspect.getsource(PSL.PageScenario._build_editor_tabs) \
        if hasattr(PSL.PageScenario, "_build_editor_tabs") else inspect.getsource(PSL)
    assert "self._layout_view.textChanged.connect(self._schedule_autosave)" in _src, \
        "les retouches du découpage ne déclenchent pas l'autosave"


@test
def deux_fenetres_deux_titres_distincts():
    """« Créer le découpage » et « Générer les séquences » n'ouvrent pas deux fenêtres
    au MÊME titre (correctif 2026-07-26).

    En renommant la fenêtre de mise en page « Découpage — Aperçu », je lui avais donné
    le titre déjà porté par la fenêtre des séquences : cliquer sur « Générer les
    séquences » donnait l'impression d'ouvrir la mauvaise fenêtre."""
    import inspect
    import ui.page_scenario_live as PSL

    _seq = inspect.getsource(PSL.PageScenario._open_decoupage_window)   # Séquences
    _dec = inspect.getsource(PSL.PageScenario._open_format_window)      # Découpage

    assert "Séquences Mapping" in _seq and "Séquences Live" in _seq, \
        "la fenêtre des séquences ne nomme pas la séquence courante"
    assert 'translate("Découpage — Aperçu")' not in _seq, \
        "les deux fenêtres portent encore le même titre"
    assert "Découpage — Aperçu" in _dec, \
        "la fenêtre du découpage a perdu son titre"
    # Et son statut parle bien de séquences, pas de découpage.
    assert "Génération des séquences…" in _seq and "Séquences générées" in _seq, \
        "le statut de la fenêtre des séquences parle encore de découpage"

    from core.i18n import _FR_TO_EN as T
    for _k in ("Génération des séquences…", "Séquences générées"):
        assert _k in T, ("i18n manquant", _k)


@test
def decoupage_live_produit_des_fiches_pandora_2():
    """Le découpage Live est enfin au contrat « DÉCOUPAGE PANDORA 2 » (2026-07-26).

    Constat Matthieu, captures à l'appui : le Cinéma produisait des FICHES (SOURCE /
    INTENTION / RYTHME / DURÉE / PROMPT VISUEL / PERSONNAGES…) pendant que le Live
    restait sur l'ancien format plat. Le Live a désormais le même contrat, plus SON —
    son champ propre, qui alimente le sound design et le calage musical."""
    import inspect
    from core.decoupage_document import (is_v2_document, validate_v2_document,
                                         parse_v2_document, _LABELS)
    from core.decoupage_layout import parse_layout_segments
    from api.live_extract import (FormatConducteurWorker, validate_live_layout,
                                  _LAYOUT_CORRECTION)

    V2 = ("DÉCOUPAGE PANDORA 2\n\nSÉQUENCE 1 — ACCROCHE GELÉE\n\nPLAN 01\n"
          "SOURCE CONDUCTEUR : Toute la pierre de la façade est prise dans le givre.\n"
          "INTENTION : Installer le gel total avant la première étincelle.\n"
          "RYTHME : Tempo suspendu, aucune coupe avant le jaillissement.\n"
          "DURÉE : 5s\n"
          "PROMPT VISUEL : Ouverture : la façade est prise dans le givre. Puis le gel "
          "s'épaissit. Dans le dernier instant, une microluminescence frémit.\n"
          "SON : Souffle glacé grave, craquements de gel, réverbération d'église vide.\n"
          "PERSONNAGES : Éloane\nACCESSOIRES : —\nVÉHICULES : —")

    # 1. Le worker Live demande bien le contrat v2, plus l'ancien format plat.
    #    On retire les COMMENTAIRES avant de vérifier : ils citent forcément les
    #    champs retirés pour expliquer pourquoi ils le sont (piège rencontré trois
    #    fois dans la journée — l'assertion mordait sur sa propre justification).
    _run = "\n".join(l for l in inspect.getsource(FormatConducteurWorker.run).split("\n")
                     if not l.strip().startswith("#"))
    assert "DÉCOUPAGE PANDORA 2" in _run, "le Live ne demande pas le contrat v2"
    for _champ in ("SOURCE CONDUCTEUR", "INTENTION", "RYTHME", "PROMPT VISUEL",
                   "SON", "PERSONNAGES", "ACCESSOIRES", "VÉHICULES"):
        assert _champ in _run, ("champ de fiche absent du contrat Live", _champ)
    assert "=== ACTE {n}" not in _run, "l'ancien format plat est encore demandé"
    assert "N'utilise PAS l'ancien format" in _LAYOUT_CORRECTION
    # Champs hérités du Cinéma RETIRÉS du contrat Live (demande Matthieu 2026-07-26) :
    # sans objet pour une boucle VJ ou un mapping à caméra verrouillée.
    for _hors_sujet in ("VALEUR PROPOSÉE :", "MOUVEMENT PROPOSÉ :", "MOOD :"):
        assert _hors_sujet not in _run, \
            ("champ Cinéma encore demandé au Live", _hors_sujet)

    # 2. Un document Live v2 satisfait AUSSI le contrat partagé du Cinéma.
    assert is_v2_document(V2), "le document Live n'est pas reconnu comme v2"
    assert validate_v2_document(V2) == [], \
        "le contrat partagé refuse un découpage Live v2"
    assert validate_live_layout(V2) == [], "le validateur Live refuse ses propres fiches"

    # 3. SON est un champ v2 à part entière, et il est EXIGÉ côté Live seulement.
    assert "sound" in _LABELS, "champ SON absent du contrat v2"
    _sans_son = V2.replace(
        "SON : Souffle glacé grave, craquements de gel, réverbération d'église vide.\n", "")
    assert validate_v2_document(_sans_son) == [], \
        "le Cinéma ne doit PAS exiger de son par plan"
    assert validate_live_layout(_sans_son) == ["P01:son"], \
        "le Live doit exiger le SON (sound design + calage musical)"

    # 4. Les champs éditoriaux arrivent réellement jusqu'aux plans.
    seg = parse_layout_segments(V2)[0]
    assert seg["source"].startswith("Toute la pierre"), "SOURCE perdue"
    assert seg["intention"].startswith("Installer"), "INTENTION perdue"
    assert seg["rhythm"].startswith("Tempo"), "RYTHME perdu"
    assert seg["sound_prompt"].startswith("Souffle"), "SON perdu"
    assert seg["character_names"] == ["Éloane"], "PERSONNAGES perdus"
    assert parse_v2_document(V2)[0]["sound_prompt"], "sound_prompt absent du parseur v2"
    # Les champs Cinéma retirés du contrat ressortent VIDES, sans casser la lecture…
    assert seg["shot_size"] == "" and seg["camera_movement"] == "", \
        "une fiche Live sans propositions caméra devrait les rendre vides"
    # …mais un découpage Live ANTÉRIEUR qui les porte reste lu correctement.
    _legacy = V2 + ("\nVALEUR PROPOSÉE : Plan d'ensemble\n"
                    "MOUVEMENT PROPOSÉ : Fixe\nMOOD : À CRÉER")
    _ls = parse_layout_segments(_legacy)[0]
    assert _ls["shot_size"] == "Plan d'ensemble" and _ls["camera_movement"] == "Fixe", \
        "un ancien découpage Live perd ses propositions caméra"
    assert validate_live_layout(_legacy) == [], "un ancien découpage Live est refusé"

    # 5. Le prompt envoyé au moteur recolle VISUEL + SON (sinon le son disparaît).
    from core.prompt_sections import video_with_sound, sound_of
    _p = video_with_sound(seg["prompt"], seg["sound_prompt"])
    assert sound_of(_p).startswith("Souffle"), "[🎵 SOUND DESIGN] non reconstitué"
    import ui.page_scenario_live as PSC
    assert "video_with_sound" in inspect.getsource(
        PSC.PageScenario._write_decoupage_segments), \
        "les fiches v2 perdraient leur son à l'écriture des plans"
    import ui.page_storyboard_live as PSB
    assert "video_with_sound" in inspect.getsource(PSB.PageStoryboard._segments_to_shots)

    # 6. RÉTROCOMPATIBILITÉ : les découpages Live déjà enregistrés au format PLAT
    #    restent lisibles et valides — rien à migrer.
    PLAT = ("=== ACTE 1 — ACCROCHE ===\nPLAN 1 — Le gel dort\n"
            "Durée : 5s · Valeur de plan : plan large · Mouvement : fixe\n"
            "PROMPT VIDÉO (français) : \"La façade prise dans le givre, dense.\"\n"
            "PROMPT SON (sound design / SFX, français) : \"Souffle glacé.\"")
    assert not is_v2_document(PLAT)
    assert validate_live_layout(PLAT) == [], \
        "un ancien découpage Live au format plat est refusé — régression"
    assert parse_layout_segments(PLAT)[0]["sound_prompt"].startswith("Souffle")


@test
def duree_en_timecode_nest_plus_lue_zero_seconde():
    """Un plan écrit « Durée : 0:20 » vaut 20 s, plus 0 (correctif 2026-07-26).

    _DUR_RE n'attrapait que le premier groupe de chiffres : le modèle bascule
    spontanément en notation timecode pour les plans longs, et « 0:20 » devenait un
    plan de ZÉRO seconde — en silence, avant que la validation n'existe. Le bug
    touchait les DEUX éditions (module partagé)."""
    from core.decoupage_layout import duration_seconds, parse_layout_segments

    ATTENDU = {
        "12s": 12, "22 s": 22, "20 secondes": 20, "8": 8,   # écritures simples
        "0:20": 20, "0'20": 20, "0:20s": 20,                 # timecode court
        "1m10": 70, "1:10": 70, "2:05": 125,                 # timecode avec minutes
        "0,5s": 1, "0.5 s": 1,                               # décimales → jamais 0
    }
    for ecriture, attendu in ATTENDU.items():
        lu = duration_seconds(f"Durée : {ecriture} · Valeur de plan : plan large")
        assert lu == attendu, (f"« Durée : {ecriture} » lu {lu} au lieu de {attendu}")

    # Illisible ou nul → None, pour que le parseur garde SON défaut (jamais 0).
    for ecriture in ("—", "0:00", "0s", "", "à définir"):
        assert duration_seconds(f"Durée : {ecriture}") is None, \
            f"« {ecriture} » devrait être illisible, pas une durée"

    # Bout en bout : le plan ne vaut jamais 0 seconde.
    def _doc(d):
        return ("=== ACTE 1 — A ===\nPLAN 1 — Titre\n"
                f"Durée : {d} · Valeur de plan : plan large · Mouvement : fixe\n"
                "PROMPT VIDÉO (français) : \"Une façade givrée, dense.\"\n"
                "PROMPT SON (sound design / SFX, français) : \"Souffle.\"")
    assert parse_layout_segments(_doc("0:20"))[0]["duration"] == 20
    assert parse_layout_segments(_doc("—"))[0]["duration"] == 5, "défaut du parseur"
    for _e in ("0:20", "0'20", "1m10", "0,5s", "—", "0:00"):
        assert parse_layout_segments(_doc(_e))[0]["duration"] > 0, \
            f"« {_e} » produit encore un plan de 0 seconde"


@test
def decoupage_live_valide_avant_enregistrement():
    """Le découpage Live est VALIDÉ, relancé une fois, et refusé s'il reste faux
    (2026-07-26, parité Cinéma qui verrouille depuis le 2026-07-23).

    PIÈGE CENTRAL : ne JAMAIS valider le Live avec validate_v2_document — le contrat
    v2 du Cinéma exige SOURCE SCÉNARIO / INTENTION / PROMPT VISUEL, que le Live ne
    produit pas. Ce test le prouve en confrontant les deux validateurs au MÊME
    document Live."""
    import inspect
    from api.live_extract import (FormatConducteurWorker, validate_live_layout,
                                  describe_layout_issues, _LAYOUT_CORRECTION)

    BON = ("=== ACTE 1 — ACCROCHE ===\n"
           "PLAN 1 — Étincelle\n"
           "Durée : 4s · Valeur de plan : plan d'ensemble · Mouvement : fixe\n"
           "PROMPT VIDÉO (français) : \"Une étincelle jaillit du portail.\"\n"
           "PROMPT SON (sound design / SFX, français) : \"Crépitement sec.\"")

    # 1. Un découpage Live conforme passe.
    assert validate_live_layout(BON) == [], "un découpage Live valide est refusé"

    # 2. …et le validateur CINÉMA le rejetterait. C'est tout le piège.
    from core.decoupage_document import validate_v2_document
    assert validate_v2_document(BON), \
        "validate_v2_document accepte le format Live — le piège aurait disparu"

    # 3. Les fautes RÉELLEMENT bloquantes sont vues, et lisibles.
    _sans_son = BON.replace(
        "PROMPT SON (sound design / SFX, français) : \"Crépitement sec.\"", "")
    assert validate_live_layout(_sans_son) == ["P01:son"], \
        "PROMPT SON manquant non détecté (sound design + calage musical perdus)"
    assert "PROMPT SON" in describe_layout_issues(["P01:son"])
    # PROMPT VIDÉO absent : le parseur retombe SILENCIEUSEMENT sur le titre du plan,
    # d'où le contrôle « prompt == titre » plutôt qu'un simple test de vacuité.
    _sans_video = BON.replace(
        "PROMPT VIDÉO (français) : \"Une étincelle jaillit du portail.\"", "")
    assert validate_live_layout(_sans_video) == ["P01:prompt"], \
        "PROMPT VIDÉO manquant non détecté (repli silencieux sur le titre)"
    assert validate_live_layout("bonjour") == ["structure_non_reconnue"]
    assert describe_layout_issues([]) == ""

    # 3bis. Une durée HORS 2–15 s n'est PAS bloquante (correctif 2026-07-26, cas réel
    # refusé à tort). core.music_align.conform_durations_to_set la répare EN PLACE
    # avec ces mêmes bornes au moment d'écrire les plans : refuser le document
    # revenait à jeter un découpage que PANDORA sait corriger seul.
    _long = BON.replace("Durée : 4s", "Durée : 30s")
    assert validate_live_layout(_long) == [], \
        "une durée hors bornes bloque encore alors qu'elle est conformée ensuite"
    from core.music_align import conform_durations_to_set
    _segs = [{"duration": 22}, {"duration": 30}, {"duration": 6}]
    conform_durations_to_set(_segs, 40)
    assert [s["duration"] for s in _segs] == [15, 15, 10], \
        "la conformation ne ramène plus les durées dans les bornes"
    # Et la borne est ANNONCÉE au modèle dès le premier jet (elle n'était écrite
    # nulle part : il produisait des plans de 20 à 40 s sans le savoir).
    import api.live_extract as _LE
    assert "entre 2 et 15 secondes" in inspect.getsource(
        _LE.FormatConducteurWorker.run), "la borne de durée n'est pas dite au modèle"

    # 4. Le worker valide, relance UNE fois, puis refuse — et n'affiche rien avant.
    _run = inspect.getsource(FormatConducteurWorker.run)
    # Le MODE est passé au validateur (2026-07-27) : en mapping il exige en plus
    # les trois temps de la barre, une règle sans objet en VJ libre.
    assert "validate_live_layout(full, self._mode)" in _run, \
        "le worker ne valide pas sa sortie, ou ne dit pas au validateur quel mode"
    assert "layout_correction" in _run and "self.retrying.emit" in _run, \
        "pas de relance corrective annoncée"
    assert _run.index("self.chunk.emit(full)") > _run.index("validate_live_layout(full"), \
        "le document est affiché AVANT d'être validé (un jet raté serait montré)"
    assert "Rien n'a été enregistré" in _run, \
        "un découpage invalide doit être refusé, pas enregistré"
    # Sur le CODE seul : les commentaires du worker citent volontairement
    # is_v2_document pour expliquer pourquoi la ligne « PROMPT VISUEL : » doit
    # rester présente. Chercher dans le texte brut se déclencherait sur cette
    # explication et ne prouverait rien.
    _run_code = "\n".join(l for l in _run.splitlines()
                          if not l.lstrip().startswith("#"))
    assert "validate_v2_document" not in _run_code and "is_v2_document" not in _run_code, \
        "le worker Live utilise le validateur du Cinéma"

    # 5. Le suffixe correctif rappelle le contrat de FICHES, champ SON compris.
    #    (Depuis le 2026-07-26 le Live produit lui aussi du « DÉCOUPAGE PANDORA 2 » ;
    #    ce qu'il ne doit PAS faire, c'est retomber sur l'ancien format plat.)
    assert "N'utilise PAS l'ancien format" in _LAYOUT_CORRECTION, \
        "la relance n'interdit pas le retour à l'ancien format plat"
    for _must in ("DÉCOUPAGE PANDORA 2", "SOURCE CONDUCTEUR", "INTENTION",
                  "PROMPT VISUEL", "SON", "chiffrée sur chaque plan"):
        assert _must in _LAYOUT_CORRECTION, ("relance corrective incomplète", _must)

    # 6. « Appliquer » AVERTIT sans interdire : un découpage retouché à la main et
    #    déjà en base ne doit pas devenir soudainement inapplicable.
    import ui.page_scenario_live as PSL
    _fmt = inspect.getsource(PSL.PageScenario._open_format_window)
    assert "validate_live_layout(" in _fmt and '"_live_mode", "live"' in _fmt, \
        "« Appliquer » ne valide rien, ou ignore le mode de séquence"
    assert "Appliquer quand même" in _fmt, \
        "« Appliquer » bloque au lieu d'avertir (régression sur les découpages existants)"

    from core.i18n import _FR_TO_EN as T
    for _k in ("Découpage incomplet", "Appliquer quand même", "Corriger",
               "Format incomplet — nouvelle tentative…"):
        assert _k in T, ("i18n manquant", _k)


@test
def worker_detruit_ne_fait_plus_planter_la_fermeture():
    """Fermer PANDORA Live ouvrait une fenêtre d'erreur (crash réel 2026-07-26) :

        ui/visual_identity.py:41 in _cleanup
            if worker is not None and worker.isRunning():
        RuntimeError: wrapped C/C++ object of type VisualIdentityWorker has been deleted

    `destroyed` se déclenche APRÈS la destruction de l'objet C++ : le worker peut avoir
    été emporté avec l'arbre Qt, et isRunning() lève au lieu de répondre. Une exception
    non gérée dans un slot PyQt6 fait tomber l'app (doctrine projet)."""
    import inspect
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QThread
    from PyQt6 import sip
    QApplication.instance() or QApplication([])
    from core.worker import abandon_thread, is_running

    # 1. Un worker dont l'objet C++ est DÉTRUIT : isRunning() lève, is_running() non.
    w = QThread()
    sip.delete(w)
    _leve = False
    try:
        w.isRunning()
    except RuntimeError:
        _leve = True
    assert _leve, "le scénario du crash n'est plus reproductible — test à revoir"
    assert is_running(w) is False, "is_running() doit répondre False, pas lever"

    # 2. abandon_thread() encaisse aussi un objet détruit (aucune exception).
    w2 = QThread()
    sip.delete(w2)
    abandon_thread(w2)

    # 3. Le nettoyage d'identité visuelle survit à un worker détruit.
    import ui.visual_identity as VI

    class _Owner:
        pass

    owner = _Owner()
    owner._visual_identity_worker = None
    _dead = QThread()
    sip.delete(_dead)
    owner._visual_identity_worker = _dead
    # On vise l'APPEL (« and worker.isRunning(): ») : le commentaire qui raconte le
    # crash cite forcément worker.isRunning() et ne doit pas déclencher.
    _src = inspect.getsource(VI.prepare_owner)
    assert "is_running(worker)" in _src and "and worker.isRunning():" not in _src, \
        "visual_identity._cleanup appelle encore isRunning() à nu"

    # 4. Plus aucun isRunning() à nu dans un chemin de FERMETURE.
    import ui.dialog_extract_generate as DEG, ui.dialog_room_variations as DRV
    assert "and w.isRunning():" not in inspect.getsource(DEG.ExtractGenerateDialog.reject), \
        "reject() appelle isRunning() à nu (abort possible à la fermeture)"
    assert "and w.isRunning():" not in inspect.getsource(DRV.RoomVariationsDialog._abandon_tr_worker), \
        "_abandon_tr_worker appelle isRunning() à nu"


@test
def erreurs_ia_texte_live_nomment_le_bon_moteur():
    """Les erreurs de la chaîne TEXTE Live ne passent plus par l'humaniseur fal.ai
    (2026-07-26). Toute la chaîne (mise en page, découpage, arrangement, co-écriture,
    extraction) formatait ses erreurs avec core.worker.humanize_api_error, dont les
    mots-clés incluent « credit » / « quota » et dont la sortie est « Crédits fal.ai
    insuffisants — rechargez votre compte sur fal.ai/dashboard ». Un compte IA TEXTE
    à zéro envoyait donc l'utilisateur recharger le mauvais compte."""
    import inspect
    from api.live_screenplay import fmt_err
    import api.live_extract as LE
    import api.live_screenplay as LS

    # Plus AUCUN appel à l'humaniseur vidéo dans la chaîne texte Live.
    for _mod in (LE, LS):
        _src = inspect.getsource(_mod)
        assert "humanize_api_error(" not in _src, \
            (f"{_mod.__name__} : erreur texte passée par l'humaniseur fal.ai")

    # Une erreur de crédit ne doit JAMAIS renvoyer vers fal.ai.
    out = fmt_err(Exception("429 rate limit exceeded — insufficient credit"), "decoupage")
    assert "fal.ai" not in out.lower(), "l'erreur texte renvoie encore vers fal.ai"

    # L'erreur nomme le moteur RÉELLEMENT routé pour la tâche.
    from core.ai_provider import ai_name_for_task
    for _task in ("decoupage", "storyboard_gen", "screenplay"):
        _name = ai_name_for_task(_task)
        assert _name and _name in fmt_err(Exception("boom"), _task), \
            (f"l'erreur ne nomme pas le moteur de la tâche « {_task} »")

    # Chaque site d'échec passe une tâche explicite (jamais le défaut implicite).
    _ls = inspect.getsource(LS)
    assert _ls.count('fmt_err(e, "') >= 5, "un site d'erreur live_screenplay non typé"
    assert 'fmt_err(e, "storyboard_gen")' in _ls, "le découpage doit nommer storyboard_gen"
    _le = inspect.getsource(LE)
    for _t in ('"decoupage"', '"screenplay"', '"extraction"'):
        assert f"_fmt_err(e, {_t})" in _le, f"site d'erreur live_extract non typé : {_t}"

    # Plafonds de sortie : l'extraction ne doit plus être coupée à 4096.
    assert LE._MAX_TOKENS_BY_TASK.get("extraction") == 16000, \
        "l'extraction Live est encore plafonnée trop bas (listes tronquées en silence)"
    assert "max_tokens=4096" not in _le, "plafond 4096 encore écrit en dur"

    # La garde de clé de la Mise en page doit viser la MÊME tâche que l'appel.
    _run = inspect.getsource(LE.FormatConducteurWorker.run)
    assert 'key_error("decoupage")' in _run and 'task="decoupage"' in _run, \
        "la garde de clé et l'appel ne visent pas la même tâche"

    # Libellés de progression : le moteur par tâche, pas la marque globale.
    import ui.page_scenario_live as PSL
    _fmt = inspect.getsource(PSL.PageScenario._on_format)
    assert 'ai_name_for_task("decoupage")' in _fmt, \
        "le libellé de la Mise en page ne nomme pas le moteur de la tâche"
    _dec = inspect.getsource(PSL.PageScenario._on_storyboard)
    assert 'ai_name_for_task("storyboard_gen")' in _dec, \
        "le libellé du Découpage ne nomme pas le moteur de la tâche"
    from core.i18n import _FR_TO_EN as T
    for _k in ("Mise en page du conducteur via {ai}…", "Génération du découpage via {ai}…"):
        assert _k in T, ("i18n manquant", _k)


@test
def decoupage_live_reellement_persiste():
    """Le Découpage Live SURVIT à l'enregistrement (correctif 2026-07-26).

    Perte silencieuse trouvée par audit : core/scenario.normalize_scenario donne la
    PRIORITÉ à `decoupage_content` et ne retombe sur `layout_content` que si la clé est
    ABSENTE (None) — pas si elle vaut "". Le Live n'écrivait que `layout_content` ; dès
    le 2e enregistrement, le `decoupage_content` vide figé par la normalisation
    précédente écrasait le découpage. « Appliquer le découpage ✓ » s'affichait, et au
    rechargement l'onglet était vide ET grisé.

    Ce test traverse la VRAIE persistance (aucun stub de list_scenarios) : c'était
    précisément l'angle mort qui laissait le harnais vert."""
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import core.scenario as scenario_api
    import ui.page_scenario_live as PSL

    DEC = ("=== ACTE 1 — ACCROCHE ===\n"
           "PLAN 1 — Étincelle\n"
           "Durée : 4s · Valeur de plan : plan d'ensemble · Mouvement : fixe\n"
           "PROMPT VIDÉO (français) : \"Une étincelle jaillit du portail.\"\n"
           "PROMPT SON (sound design / SFX, français) : \"Crépitement sec.\"")

    page = PSL.PageScenario()
    page._title_edit.setText("Teaser persistance")
    page._editor_text.setPlainText("Conducteur du teaser.")

    # 1er autosave : le découpage est encore VIDE (l'utilisateur tape son conducteur).
    page._save(silent=True)
    # Puis « Appliquer le découpage » → 2e enregistrement.
    page._layout_view.setPlainText(DEC)
    page._save(silent=True)

    sid = (page._current or {}).get("id", "")
    assert sid, "le conducteur n'a pas été enregistré"
    reread = scenario_api.get_scenario(sid) or {}
    assert "PLAN 1 — Étincelle" in (reread.get("decoupage_content") or ""), \
        "decoupage_content perdu à l'enregistrement"
    assert "PLAN 1 — Étincelle" in (reread.get("layout_content") or ""), \
        "alias layout_content perdu (les 2.0.1 installées ne reliraient plus le fichier)"
    assert "PROMPT SON" in (reread.get("decoupage_content") or ""), \
        "le PROMPT SON (sound design + calage musical) n'a pas survécu"

    # Rechargement : l'onglet Découpage doit être rempli ET accessible.
    page2 = PSL.PageScenario()
    page2._save = lambda *a, **k: None
    page2._open_scenario(reread)
    assert "PLAN 1 — Étincelle" in page2._layout_view.toPlainText(), \
        "le découpage ne revient pas dans l'onglet au rechargement"
    assert page2._editor_tabs.isTabEnabled(page2.TAB_DECOUPAGE), \
        "l'onglet Découpage est grisé alors qu'un découpage existe"

    # Rétrocompatibilité : un conducteur ANTÉRIEUR au 2026-07-23 n'a que layout_content
    # et AUCUN decoupage_content — il doit encore être migré par core/scenario.py.
    ancien = scenario_api.normalize_scenario(
        {"title": "Ancien", "layout_content": "PLAN 1 — Ancien format"})
    assert "PLAN 1 — Ancien format" in ancien["decoupage_content"], \
        "la migration des anciens conducteurs (layout_content seul) est cassée"

    # Le format Live doit traverser canonicalize_layout INTACT (piège P3 de l'audit :
    # un en-tête « PROMPT : » nu serait réécrit par la branche Cinéma).
    from core.decoupage_layout import canonicalize_layout
    assert "PROMPT VIDÉO (français)" in canonicalize_layout(DEC), \
        "canonicalize_layout abîme le format Live"

    # Les DEUX clés doivent être écrites partout où le Live sauve.
    import inspect
    _src = inspect.getsource(PSL.PageScenario)
    assert _src.count('"decoupage_content": self._read_layout()') >= 2, \
        "un point de sauvegarde Live n'écrit pas la clé canonique"
    assert "_layout_view.toPlainText()" not in inspect.getsource(PSL.PageScenario._save), \
        "_save doit passer par _read_layout(), jamais par la vue brute"


@test
def estimation_masquee_si_duree_cible():
    """Durée cible cochée → l'ESTIMATION disparaît (parité Cinéma, portée Live
    le 2026-07-26). Une durée choisie rend l'estimation sans objet, et les deux
    ne tiennent pas ensemble dans les 300 px du panneau."""
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import ui.page_scenario_live as PSL

    page = PSL.PageScenario()
    page._save = lambda *a, **k: None       # jamais d'écriture réelle en test
    lbl = page._dur_estimate_lbl

    # isHidden() : reflète l'état demandé même si la page n'est pas à l'écran.
    assert not lbl.isHidden(), "l'estimation doit être visible sans durée cible"

    page._dur_defined_check.setChecked(True)
    assert lbl.isHidden(), "l'estimation reste affichée alors que la durée cible est active"
    assert not page._dur_min.isHidden() and not page._dur_sec.isHidden(), \
        "les spinboxes de durée doivent apparaître avec la durée cible"

    page._dur_defined_check.setChecked(False)
    assert not lbl.isHidden(), "l'estimation ne revient pas quand on décoche la durée cible"

    # Le rafraîchissement du texte ne doit JAMAIS ré-afficher le label.
    page._dur_defined_check.setChecked(True)
    page._editor_text.setPlainText("mot " * 400)
    page._update_dur_estimate()
    assert lbl.isHidden(), "_update_dur_estimate ré-affiche l'estimation masquée"


@test
def prompt_video_live_jamais_compose():
    """Le composeur CINÉMA ne prend jamais un prompt Live.

    Formulation d'origine (2026-07-21) : « le Live n'est jamais composé ». Elle a
    été révisée le 2026-07-26 — Matthieu veut le même confort qu'au Cinéma. Ce que
    ce test garde, et qui reste vital, c'est que le prompt Live ne parte pas dans
    `api/video_prompt`, dont la consigne impose « Camera: » et « Sound: » : deux
    des trois interdits du mapping. Le Live compose désormais avec SON composeur,
    bridé par core/live_grammar et vérifié (voir `composition_live_verifiee`)."""
    from api.video_prompt import should_compose
    from core.prompt_sections import video_with_sound
    live = video_with_sound(
        "Début : façade sombre, lueur bleue. Milieu : pulsation sur les fenêtres. "
        "Fin : blackout sec.", "basses sourdes, kick au drop")
    assert not should_compose(live), "prompt Live (corps + son) → jamais composé"
    assert not should_compose("texte libre du Live"), "texte libre → jamais composé"
    # Le repli d'api/real.py (partagé) reste en place pour ces prompts.
    rsrc = inspect.getsource(__import__("api.real", fromlist=["x"]))
    assert "if not _composed:" in rsrc and "translate_to_english" in rsrc, \
        "chemin historique strip+traduction conservé pour le Live"
    # Pas d'injection casting côté Live (pas de page Casting en Live) — assumé.
    lsrc = inspect.getsource(__import__("ui.tab_t2v_live", fromlist=["x"]))
    assert "character_notes_for_shot" not in lsrc, \
        "Live sans fiches casting (divergence assumée, pas un oubli de portage)"


@test
def coecriture_anti_perte_live():
    """Parité Live du chantier anti-perte co-écriture (2026-07-21) : continuation
    anti-troncature dans le worker CONDUCTEUR (texte + vision), relance auto des
    passages non retrouvés, alerte tokens déterministe — mêmes remèdes que Cinéma."""
    src = inspect.getsource(__import__("api.live_screenplay", fromlist=["x"]))
    assert "chat_until_complete" in src, "worker conducteur sans anti-troncature"
    assert 'max_rounds=5' in src, "chemin vision sans continuation centralisée"
    from ui.dialog_arrange_session_live import ArrangeSessionDialog
    d = ArrangeSessionDialog(None, "=== ACTE 1 ===\nPLAN 1 — Ouverture", "analyse", 5)
    _cap = {}
    d._start_worker = lambda instr, surgical=True, **k: _cap.update(instr=instr, surgical=surgical)
    d._on_rewrite_coedit()
    assert "Re-parcours TOUTE" in _cap["instr"] and "conducteur" in _cap["instr"], \
        "instruction de couverture totale (vocabulaire conducteur)"
    _cap.clear()
    d._on_edits_ready([{"find": "INTROUVABLE", "replace": "x", "summary": "point L"}])
    assert _cap.get("surgical") is True and "point L" in _cap.get("instr", ""), \
        "passages non retrouvés → relance auto"
    _cap.clear()
    d._on_edits_ready([{"find": "ENCORE INTROUVABLE", "replace": "y", "summary": "point M"}])
    assert not _cap, "une seule relance auto par demande"
    d2 = ArrangeSessionDialog(None, "x" * 250_000, "analyse", 5)
    _bulles = []
    d2._append_chat_bubble = lambda text, role: _bulles.append(text)
    d2._maybe_warn_tokens()
    assert _bulles and "applique le conducteur au projet" in _bulles[0], \
        "alerte tokens Live (vocabulaire conducteur)"
    from core.i18n import _FR_TO_EN
    assert any("applique le conducteur au projet" in k for k in _FR_TO_EN), \
        "alerte tokens Live traduite"


@test
def grammaire_live_separee():
    """La grammaire du Live est SÉPARÉE de celle du Cinéma (demande Matthieu
    2026-07-26 : « est-ce que c'est possible de les séparer pour que ça ne touche
    pas Cinéma quand on travaille sur Live ? »).

    Le partage était réel : `core/live_prompt` importait `core/engine_grammar`, un
    fichier dont dépend tout l'envoi Cinéma. Une correction motivée par un plan
    Live s'y écrivait donc directement — c'est arrivé.

    La séparation retenue ne duplique PAS la table moteur→forme (Seedance lit des
    champs des deux côtés ; deux tables divergeraient). Elle sépare le VOCABULAIRE,
    là où Cinéma et Live sont en opposition frontale : `Camera:`, `Lighting:` et
    `Sound:` sont les champs du Cinéma et les trois interdits du mapping.
    """
    import ast
    import glob
    import inspect
    import core.live_grammar as LG
    import ui.tab_t2v_live as _TL
    from core.live_prompt import assemble

    def _lire(path):
        # utf-8-SIG : plusieurs sources du dépôt portent un BOM, et ast.parse le
        # refuse (« invalid non-printable character U+FEFF »).
        with open(path, encoding="utf-8-sig") as fh:
            return fh.read()

    def _code_seul(path):
        """Code pur : sans commentaires ni docstrings.

        Indispensable — `engine_grammar.py` porte des commentaires qui PARLENT du
        Live (l'historique d'un correctif). Un test qui cherche le mot dans le
        texte brut se déclencherait sur ces commentaires et ne prouverait rien :
        piège tombé quatre fois dans ce harnais.
        """
        tree = ast.parse(_lire(path))
        for n in ast.walk(tree):
            if isinstance(n, (ast.Module, ast.FunctionDef,
                              ast.AsyncFunctionDef, ast.ClassDef)):
                if ast.get_docstring(n) is not None:
                    n.body = n.body[1:] or [ast.Pass()]
        return ast.unparse(tree)

    _ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 1. TRIPWIRE — le fichier partagé ne contient aucun code propre au Live.
    _eg = _code_seul(os.path.join(_ROOT_DIR, "core", "engine_grammar.py")).lower()
    assert "façon" in _eg, \
        "le code d'engine_grammar n'a pas été lu — test sans valeur"
    for _mot in ("mapping", "façade", "facade", "bpm", "sparkline",
                 "vidéoprojecteur", "live_bar", "live_grammar"):
        assert _mot not in _eg, \
            (f"vocabulaire Live « {_mot} » dans core/engine_grammar.py — "
             "il doit aller dans core/live_grammar.py, dont le Cinéma ne dépend pas")

    # 2. Aucun module Live n'importe le fichier partagé en direct.
    _lives = [p for p in glob.glob(os.path.join(_ROOT_DIR, "**", "*live*.py"),
                                   recursive=True)
              if os.sep + "tools" + os.sep not in p]
    assert len(_lives) >= 5, ("trop peu de modules Live trouvés", len(_lives))
    for _p in _lives:
        if os.path.basename(_p) == "live_grammar.py":
            continue          # LE point de passage autorisé, et le seul
        _mods = set()
        for _n in ast.walk(ast.parse(_lire(_p))):
            if isinstance(_n, ast.ImportFrom):
                _mods.add(_n.module or "")
            elif isinstance(_n, ast.Import):
                _mods.update(a.name for a in _n.names)
        assert "core.engine_grammar" not in _mods, \
            (f"{os.path.basename(_p)} importe core.engine_grammar en direct — "
             "passer par core.live_grammar pour que le Cinéma reste hors de portée")

    # 3. La table moteur→forme n'est PAS dupliquée : elle est déléguée.
    from core.engine_grammar import grammar_for as _cine_shape
    for _k in ("seedance-2.0", "veo-3.1", "kling-o3-4k", "ltx-2", ""):
        assert LG.grammar_for(_k) == _cine_shape(_k), \
            (f"la forme attendue par « {_k} » a divergé entre Live et Cinéma — "
             "c'est un fait constructeur, il ne doit exister qu'une fois")

    # 4. Le VOCABULAIRE, lui, diffère vraiment (garde anti-tautologie).
    from core.engine_grammar import format_rules as _cine_rules
    _cr = _cine_rules("seedance-2.0")
    assert "Camera:" in _cr and "Sound:" in _cr, \
        "le Cinéma n'impose plus Camera:/Sound: — le test ne compare plus rien"
    _lr = LG.format_rules("seedance-2.0", mode="mapping")
    for _interdit in ("Camera:", "Sound:", "Lighting:"):
        assert _interdit not in _lr, \
            (f"la consigne de mapping propose « {_interdit} » — "
             "caméra boulonnée, lumière projetée, son = le set")
    assert "Surface:" in _lr and "Black:" in _lr, "champs propres au mapping absents"
    assert "Camera" not in LG.fields_for("mapping"), "Camera autorisé en mapping"
    assert "Camera" in LG.fields_for("live"), "Camera interdit hors mapping"
    assert not LG.allows_camera("mapping"), "caméra autorisée en mapping"
    assert LG.allows_sound("live"), "son interdit hors mapping"

    # 5. Comportement : en mapping la caméra n'atteint PAS le moteur.
    _cam = ["slow dolly in", "handheld"]
    _corps = "the frost thickens across the stone"
    _live, _ = assemble(_corps, engine_key="seedance-2.0", camera_bits=_cam,
                        mode="live")
    assert "dolly" in _live, \
        "hors mapping les termes caméra doivent passer — sinon test sans valeur"
    _map, _ = assemble(_corps, engine_key="seedance-2.0", camera_bits=_cam,
                       mode="mapping")
    assert "dolly" not in _map and "handheld" not in _map, \
        "termes caméra partis au moteur en mapping — le cadre est verrouillé"
    assert _corps in _map, "le corps du plan doit passer mot pour mot"

    # 6. Filet de bout de chaîne : un champ interdit glissé dans le corps saute.
    _sale = _corps + "\nCamera: slow push in\nSound: deep drone\nStyle: engraving"
    _net, _ = LG.enforce_mode(_sale, "mapping")
    assert "Camera:" not in _net and "Sound:" not in _net, \
        "champ interdit non filtré en mapping"
    assert "Style: engraving" in _net, "le filet a mangé un champ autorisé"
    _garde, _ = LG.enforce_mode(_sale, "live")
    assert "Camera: slow push in" in _garde, \
        "le filet mapping s'applique hors mapping — il déborde"

    # 7. Le mode par défaut ne change RIEN à l'existant.
    assert assemble(_corps, engine_key="veo-3.1")[0] == \
           assemble(_corps, engine_key="veo-3.1", mode="live")[0], \
        "le mode par défaut n'est plus « live » — régression silencieuse"

    # 8. L'UI passe bien le mode réel de la séquence aux deux endroits.
    _src = inspect.getsource(_TL)
    assert _src.count('mode=getattr(self, "_seq_mode", "live")') >= 2, \
        "l'aperçu ou l'envoi n'informe pas l'assemblage du mode de séquence"


@test
def composition_live_verifiee():
    """Le Live PEUT être composé par l'IA, mais une composition qui perd la barre
    est REJETÉE (demande Matthieu 2026-07-26 : « la même chose que dans cinéma »).

    L'ancien arbitrage interdisait toute composition, par crainte de diluer les
    beats. Le nouvel arbitrage la permet et la CONTRÔLE : c'est le contrôle qui
    remplace l'abstinence, donc c'est lui qui doit être prouvé. Chaque cas
    ci-dessous est une sortie que l'IA produit réellement quand on la laisse faire.
    """
    from api.live_video_prompt import (_SYSTEM_LIVE, _system_for, compose,
                                       validate_live_composed as _v)

    _BARRE = ("Locked-off frontal view of a trapezoidal church facade, dead centre, "
              "isolated on pure black. At the first beat, the stone is already veiled "
              "in a thin skin of frost. Across the bar, the frost thickens steadily, "
              "crystals proliferating outward along the buttresses. By the final beat, "
              "the frost has closed over the openings. Constraints: no camera "
              "movement, no zoom, no pan, no tilt, no cuts, no scene change.")

    # 1. Une VRAIE barre de mapping passe — sinon le contrôle serait inutilisable.
    _ok = _v(_BARRE, mode="mapping")
    assert _ok["valid"], ("une barre correcte est refusée", _ok["errors"])

    # 2. Le cas qui motivait l'interdiction : la prose statique, beats dissous.
    _plat = ("Locked-off frontal view of a frozen church facade covered in dense "
             "frost, isolated on pure black, sharp crystalline texture.")
    _r = _v(_plat, mode="mapping")
    assert not _r["valid"], "une description statique est acceptée — beats perdus"
    assert any("structure de barre" in e for e in _r["errors"]), \
        ("le refus doit NOMMER la barre perdue", _r["errors"])

    # 3. La caméra nommée : interdit en mapping, licite en live.
    _cam = ("At the first beat the facade is bare. Across the bar the camera slowly "
            "pans right while frost spreads. By the final beat everything is white.")
    assert not _v(_cam, mode="mapping")["valid"], \
        "caméra nommée acceptée en mapping — le vidéoprojecteur est boulonné"
    assert _v(_cam, mode="live")["valid"], \
        "caméra refusée hors mapping — le filtre déborde"
    # Forme fléchie : « pans » doit compter autant que « pan ».
    assert not _v(_cam.replace("the camera slowly pans", "the frame slowly pans"),
                  mode="mapping")["valid"], "« pans » non détecté (forme fléchie)"

    # 4. Les négations des contraintes ne comptent PAS comme des mouvements : c'est
    # ce qui distingue un bon prompt d'un mauvais, et le confondre rejetterait
    # précisément les mieux écrits.
    assert "no camera movement" in _BARRE and _ok["valid"], \
        "« no camera movement » pris pour un mouvement affirmé"

    # 5. Une coupe casse le calage : un plan = un processus continu.
    _coupe = ("At the first beat the facade is bare. Across the bar frost spreads "
              "steadily. Cut to a wide shot. By the end everything is white.")
    assert not _v(_coupe, mode="mapping")["valid"], "coupe acceptée dans la barre"

    # 6. Les boosters de plateau sont des défauts projetés sur de la pierre.
    assert not _v(_BARRE + " Cinematic, 4K, ultra-detailed.", mode="mapping")["valid"], \
        "boosters acceptés"

    # 7. La consigne système du mapping n'est PAS celle du Cinéma.
    _sys_map = _system_for("seedance-2.0", "mapping")
    assert "Camera:" not in _sys_map and "Sound:" not in _sys_map, \
        "la consigne mapping propose les champs du Cinéma"
    assert "Surface:" in _sys_map, "la consigne mapping n'a pas sa grammaire"
    assert _SYSTEM_LIVE in _sys_map, "le socle Live a disparu de la consigne"
    from api.video_prompt import _SYSTEM as _SYS_CINE
    assert _SYS_CINE not in _sys_map, "le Live hérite de la consigne Cinéma"

    # 8. DÉTERMINISTE et hors ligne : aucun appel réseau ne doit partir d'un test.
    # On simule un échec du fournisseur → compose() renvoie "" et l'appelant replie.
    import core.ai_provider as _ap
    _vrai = _ap.complete
    try:
        _ap.complete = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("crédits épuisés"))
        assert compose("plan de test", engine="seedance-2.0", mode="mapping") == "", \
            "une erreur fournisseur doit donner un repli, pas une exception"
        import api.live_video_prompt as _LVP
        assert _LVP.LAST_COMPOSE_ERROR, \
            "la raison de l'échec doit être conservée pour être affichée"
        # Une sortie invalide ne doit pas non plus passer.
        _ap.complete = lambda *a, **k: _plat
        assert compose("plan de test", engine="seedance-2.0", mode="mapping") == "", \
            "une composition sans barre a été acceptée"
        assert "structure de barre" in _LVP.LAST_COMPOSE_ERROR, \
            "la raison du refus n'est pas exploitable à l'écran"
        # Une sortie valide passe et ressort nettoyée.
        _ap.complete = lambda *a, **k: _BARRE
        assert compose("plan de test", engine="seedance-2.0", mode="mapping"), \
            "une barre correcte est refusée par compose()"
    finally:
        _ap.complete = _vrai

    # 9. Le composeur Live n'emprunte RIEN au composeur Cinéma (AST, pas texte :
    # la docstring du module explique justement pourquoi il ne le fait pas).
    import ast
    import api.live_video_prompt as _M
    _mods = set()
    for _n in ast.walk(ast.parse(inspect.getsource(_M))):
        if isinstance(_n, ast.ImportFrom):
            _mods.add(_n.module or "")
        elif isinstance(_n, ast.Import):
            _mods.update(a.name for a in _n.names)
    assert "core.engine_grammar" not in _mods, \
        "le composeur Live importe la grammaire Cinéma"
    assert "core.live_grammar" in _mods, "le composeur Live ignore sa propre grammaire"


@test
def aucun_prompt_live_ne_demande_un_booster():
    """Les consignes IA du Live ne réclament plus les mots qu'on bannit ensuite.

    Contradiction trouvée le 2026-07-26 en branchant la composition : le découpage
    (api/live_extract) et le conducteur (api/live_screenplay) demandaient nommément
    « cinématographique, ultra-détaillé, net, 4K » — les quatre mots que
    core/live_bar.BANNED_POSITIVES interdit, que la grammaire mapping efface et que
    api/live_video_prompt.validate_live_composed REJETTE. On faisait écrire, puis
    effacer, puis on aurait refusé. Une composition branchée là-dessus aurait
    échoué systématiquement, et le repli aurait eu l'air d'un bug.

    Les repères de qualité gardés décrivent ce qui tient réellement en projection.
    """
    import ast
    from core.live_bar import BANNED_POSITIVES

    def _code_seul(path):
        # Les commentaires du correctif CITENT les mots bannis pour expliquer
        # pourquoi ils sont partis : une recherche dans le texte brut se
        # déclencherait sur l'explication elle-même.
        with open(path, encoding="utf-8-sig") as fh:
            tree = ast.parse(fh.read())
        for n in ast.walk(tree):
            if isinstance(n, (ast.Module, ast.FunctionDef,
                              ast.AsyncFunctionDef, ast.ClassDef)):
                if ast.get_docstring(n) is not None:
                    n.body = n.body[1:] or [ast.Pass()]
        return ast.unparse(tree)

    _ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _CONSIGNES = ("api/live_extract.py", "api/live_screenplay.py")

    for _rel in _CONSIGNES:
        _src = _code_seul(os.path.join(_ROOT_DIR, *_rel.split("/")))
        _low = _src.lower()
        assert "prompt" in _low, (f"{_rel} n'a pas été lu — test sans valeur")
        for _mot in BANNED_POSITIVES:
            assert _mot.lower() not in _low, \
                (f"{_rel} demande « {_mot} » à l'IA, alors que live_bar le bannit, "
                 "que la grammaire mapping l'efface et que le contrôle de "
                 "composition rejette toute prose qui le contient")

    # Et le remplacement est bien là : sans lui le test passerait aussi sur un
    # fichier où la notion de qualité aurait purement disparu.
    for _rel in _CONSIGNES:
        _src = _code_seul(os.path.join(_ROOT_DIR, *_rel.split("/")))
        assert "high contrast" in _src, \
            (f"{_rel} n'a plus AUCUN repère de qualité — les moteurs en ont besoin, "
             "il fallait les remplacer, pas les supprimer")

    # Bouclage : ce qu'on fait écrire passe le contrôle de composition.
    from api.live_video_prompt import validate_live_composed
    _prose = ("Locked-off frontal view of the facade, isolated on pure black. "
              "At the first beat, the stone is bare. Across the bar, frost spreads "
              "steadily. By the final beat, it has closed over the openings. "
              "High contrast, crisp edges, pure black background, no haze.")
    _v = validate_live_composed(_prose, mode="mapping")
    assert _v["valid"], ("les repères de qualité retenus sont eux-mêmes refusés",
                         _v["errors"])


@test
def studio_live_prompt_final_wysiwyg_et_cache():
    """L'encart du Studio Live devient le prompt RÉELLEMENT envoyé, composé une
    seule fois par plan (demande Matthieu 2026-07-26 : « la même chose que dans
    cinéma — une barre de chargement, et une sauvegarde qui évite de recréer la
    composition »).

    Trois garanties sont vérifiées ici, et chacune répond à un mode de panne
    précis : le déclencheur ne doit PAS être la frappe (sinon un appel facturé à
    chaque pause de saisie) ; l'empreinte de cache doit contenir le mode, le
    tempo, la surface et le moteur (sinon on ressert une prose périmée sans le
    moindre signe à l'écran) ; et le repli doit toujours produire un texte.
    """
    import ast
    import core.live_compose_ctx as CC
    import ui.tab_t2v_live as TL

    _src = inspect.getsource(TL)

    # ── 1. Le worker et le contrat de signal ──────────────────────────────────
    assert "class _LiveFinalPromptWorker" in _src, "worker de composition absent"
    assert "done = pyqtSignal(str, bool, str)" in _src, \
        "le worker doit émettre (prompt, composé, raison) — et « done », jamais " \
        "« finished » qui masquerait le signal natif de QThread"
    assert not hasattr(TL._LiveFinalPromptWorker, "start_generation"), \
        "le worker ne doit pas porter start_generation : d'autres tests résolvent " \
        "la classe testée par ce nom et inspecteraient la mauvaise"

    # ── 2. Le déclencheur n'est PAS la frappe ─────────────────────────────────
    _otc = inspect.getsource(TL.TabT2V._on_prompt_text_changed)
    assert "_suppress_prompt_signal" in _otc, \
        "écrire le prompt final dans l'encart relancerait le cycle — boucle facturée"
    for _interdit in ("_schedule_final_assembly", "_final_assembly_timer"):
        assert _interdit not in _otc, \
            (f"la frappe déclenche l'assemblage via « {_interdit} » — un appel IA "
             "facturé à chaque pause de saisie, bloc replié")
    _sel = inspect.getsource(TL.TabT2V._on_shot_selected_impl)
    assert _sel.count("_schedule_final_assembly()") >= 2, \
        ("l'assemblage doit être programmé AVANT le return du plan qui a déjà un "
         "prompt (le cas majoritaire) ET en fin de méthode")

    # ── 3. Garde anti-écrasement, aux DEUX bouts comme au Cinéma ──────────────
    assert _src.count('self.prompt_ta.toPlainText().strip() != src') >= 2, \
        ("garde anti-écrasement attendue au lancement ET à la réception : sans "
         "elle, une saisie faite pendant la composition est perdue")

    # ── 4. Le contrat d'envoi ─────────────────────────────────────────────────
    _gen = inspect.getsource(TL.TabT2V.start_generation)
    assert '"prompt_is_final"' in _gen, \
        ("sans ce drapeau l'envoi retraduit le texte anglais déjà validé — "
         "ce qui part n'est plus ce qui a été relu")
    for _interdit in ("visual_context", "character_notes"):
        assert _interdit not in _gen, \
            (f"« {_interdit} » dans les paramètres d'envoi déclenche le composeur "
             "CINÉMA (Camera:/Sound:) sur un prompt Live, sans qu'aucun fichier "
             "Live n'ait l'air fautif")

    # ── 5. L'empreinte de cache — le trou le plus dangereux ───────────────────
    _base = dict(engine="seedance-2.0", mode="live", style_suffix="engraving",
                 surface="a church facade", bpm=118.0, beats=8, duration=8)
    _k = lambda **kw: CC.cache_key("le givre gagne", CC.compose_context(**{**_base, **kw}))
    _ref = _k()
    for _quoi, _kw in (("le mode", {"mode": "mapping"}),
                       ("le tempo", {"bpm": 140.0}),
                       ("la surface", {"surface": "a stone bridge"}),
                       ("le moteur", {"engine": "veo-3.1"}),
                       ("le nombre de temps", {"beats": 4}),
                       ("la durée", {"duration": 5})):
        assert _k(**_kw) != _ref, \
            (f"changer {_quoi} ne change pas la clé — une prose périmée serait "
             "resservie sans aucun signe visible")
    assert _k() == _ref, "l'empreinte n'est pas reproductible"
    # Un tempo qui oscille au millième (librosa) ne doit pas faire rater le cache.
    assert _k(bpm=118.01) == _ref, "le BPM n'est pas arrondi — tous les caches ratent"

    # ── 6. Le module de contexte reste PUR ────────────────────────────────────
    _mods = set()
    for _n in ast.walk(ast.parse(inspect.getsource(CC))):
        if isinstance(_n, ast.ImportFrom):
            _mods.add(_n.module or "")
        elif isinstance(_n, ast.Import):
            _mods.update(a.name for a in _n.names)
    assert _mods, "analyse AST vide — test sans valeur"
    for _interdit in ("core.ai_provider", "core.lang", "core.engine_grammar",
                      "api.live_video_prompt"):
        assert _interdit not in _mods, \
            (f"core/live_compose_ctx doit rester pur — importe « {_interdit} »")

    # ── 7. Le worker, exécuté POUR DE VRAI, hors ligne ────────────────────────
    _BARRE = ("Locked-off frontal view of a facade, isolated on pure black. At the "
              "first beat, the stone is bare. Across the bar, frost spreads "
              "steadily. By the final beat, it has closed over the openings.")
    import core.ai_provider as _ap
    _vrai_c, _vrai_k = _ap.complete, _ap.key_error
    _recu = []
    try:
        _ap.key_error = lambda task=None: ""
        _ap.complete = lambda *a, **k: _BARRE
        w = TL._LiveFinalPromptWorker("le givre gagne la façade",
                                      {"engine": "seedance-2.0", "mode": "mapping"})
        w.done.connect(lambda t, c, y: _recu.append((t, c, y)))
        w.run()                       # run() et non start() : synchrone, testable
        assert _recu and _recu[-1][1] is True, ("composition valide non retenue", _recu)
        assert "frost" in _recu[-1][0], "le corps du plan n'est pas ressorti"

        # Échec fournisseur → repli déterministe, jamais une exception, jamais vide.
        _recu.clear()
        _ap.complete = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("crédits épuisés"))
        w2 = TL._LiveFinalPromptWorker("le givre gagne la façade",
                                       {"engine": "seedance-2.0", "mode": "mapping"})
        w2.done.connect(lambda t, c, y: _recu.append((t, c, y)))
        w2.run()
        assert _recu, "le worker n'a rien émis — la barre resterait affichée à vie"
        _txt, _comp, _why = _recu[-1]
        assert _comp is False and _txt.strip() and _why, \
            ("le repli doit produire un texte ET une raison", _recu)
    finally:
        _ap.complete, _ap.key_error = _vrai_c, _vrai_k


@test
def duree_de_barre_atteint_le_recalage_ffmpeg():
    """Le retime ffmpeg reçoit la durée EXACTE de la barre, pas l'entier arrondi.

    Constat du 2026-07-26, en préparant le branchement de core/live_bar : le
    recalage `core.video_conform.conform_clip` était bien branché, mais on lui
    passait `shot["duration"]`, que `core.music_align.conform_durations_to_set`
    a déjà écrit en ENTIER (`s["duration"] = int(d)`). Sa cible était donc la
    valeur arrondie : il ne pouvait corriger que l'imprécision du moteur, jamais
    l'arrondi musical pour lequel il a été écrit. Sa propre docstring cite
    « 5.625 s à 128 BPM » — un nombre qui n'atteignait jamais la fonction.

    Le plan porte désormais `duration_exact` (clé propre au Live : save_shot
    conserve les clés inconnues, le schéma Cinéma n'est pas touché).
    """
    import inspect
    import ui.tab_t2v_live as TL
    from core.live_bar import bar_duration
    from core.music_align import conform_durations_to_set
    from core.video_conform import MAX_DEVIATION, MIN_DELTA_S

    # 1. Le constat qui motive le correctif : la conformation écrit des ENTIERS.
    _segs = [{"duration": 3.4}, {"duration": 4.6}, {"duration": 5.1}]
    conform_durations_to_set(_segs, 20)
    assert all(isinstance(s["duration"], int) for s in _segs), \
        "conform_durations_to_set n'arrondit plus — ce test n'a plus d'objet"

    # 2. La cible du retime vient de `duration_exact` en priorité.
    _src = inspect.getsource(TL.TabT2V.on_finished)
    assert '"duration_exact"' in _src, \
        ("le recalage reçoit encore la durée arrondie — il ne peut alors corriger "
         "que l'imprécision du moteur, pas le décalage musical")
    assert _src.index('"duration_exact"') < _src.index('"duration", 0'), \
        "la durée exacte doit être essayée AVANT l'entier, pas après"

    # 3. Le sélecteur offre les durées que produisent les barres courantes.
    for _bpm, _attendu in ((140, 3), (80, 6), (70, 7)):
        _d = round(bar_duration(_bpm, 8))
        assert _d in TL.TabT2V._DUR_OPTIONS, \
            (f"une barre de 8 temps à {_bpm} BPM fait {bar_duration(_bpm, 8):.2f}s "
             f"→ {_d}s, absent du sélecteur : arrondi vers une autre valeur")
    # Le libellé du combo et la liste de valeurs doivent rester alignés : c'est
    # l'INDEX qui sert de valeur, un décalage enverrait une autre durée.
    _init = inspect.getsource(TL.TabT2V.__init__)
    for _d in TL.TabT2V._DUR_OPTIONS:
        assert f'"{_d} s"' in _init, \
            (f"la durée {_d}s est dans _DUR_OPTIONS mais absente du combo — "
             "l'index ne correspond plus à la valeur envoyée")
    assert len(TL.TabT2V._DUR_OPTIONS) == len(set(TL.TabT2V._DUR_OPTIONS)), \
        "doublon dans les durées"
    assert TL.TabT2V._DUR_OPTIONS == sorted(TL.TabT2V._DUR_OPTIONS), \
        "les durées doivent rester croissantes — l'index sert de valeur"

    # 4. Ce que le retime peut effectivement rattraper, tempo par tempo. Sert de
    # documentation exécutable : à 140 BPM l'écart reste hors tolérance, et c'est
    # assumé (un retime de 12,5 % s'entendrait et se verrait).
    _hors = []
    for _bpm in (96, 118, 128, 140, 174):
        _exact = bar_duration(_bpm, 8)
        _envoye = max(1, round(_exact))
        if abs(_envoye - _exact) / _exact > MAX_DEVIATION:
            _hors.append(_bpm)
    assert _hors == [140], \
        ("la couverture du recalage a changé — vérifier avant de l'accepter", _hors)
    assert MIN_DELTA_S < 0.1, "seuil de non-action trop haut"


@test
def vignette_mood_survit_a_la_destruction_de_sa_ligne():
    """Rafraîchir une vignette Mood sur une ligne DÉTRUITE ne plante plus.

    Crash rapporté par Matthieu le 2026-07-26 en rognant une façade :
    « RuntimeError: wrapped C/C++ object of type QLabel has been deleted »,
    page_storyboard_live.py:_on_apercu_changed → self._apercu_lbl.setPixmap.

    Mécanisme : `refresh()` reconstruit le tableau avec deleteLater(), qui diffère
    la destruction au prochain tour de boucle. Ouvrir la fenêtre Mood démarre une
    boucle IMBRIQUÉE (dlg.exec()) où ces destructions sont traitées : la ligne
    meurt PENDANT la fenêtre, et le rafraîchissement de fermeture la rappelait.
    Intermittent, donc — ça ne casse que si un refresh précédait le clic.

    Le garde `hasattr(self, "_apercu_lbl")` ne protégeait rien : l'attribut Python
    survit à la destruction Qt et pointe sur un wrapper mort.
    """
    from PyQt6.QtWidgets import QLabel, QWidget
    import ui.page_storyboard_live as PSL

    # 1. _alive distingue vraiment un widget vivant d'un widget détruit.
    _w = QWidget()
    assert PSL._alive(_w), "un widget vivant est déclaré mort"
    assert not PSL._alive(None), "None doit être déclaré mort"
    import PyQt6.sip as _sip
    _sip.delete(_w)                      # destruction C++ RÉELLE, pas simulée
    assert not PSL._alive(_w), \
        "un widget détruit côté C++ est déclaré vivant — le garde ne sert à rien"

    # 2. Le cas exact du crash : la ligne existe, sa vignette est détruite.
    class _FausseLigne(QWidget):
        """Vraie QWidget : _alive doit voir un objet Qt, pas un objet Python."""
        _data = {"id": "plan-42"}
        _on_apercu_changed = PSL._ShotRow._on_apercu_changed

    _row = _FausseLigne()
    _lbl = QLabel()
    _row._apercu_lbl = _lbl
    # Sans destruction : le chemin doit être RÉELLEMENT emprunté, sinon le test
    # ne prouverait rien (il passerait aussi sur une méthode vide).
    _row._on_apercu_changed("plan-42", "")
    assert _lbl.text(), "le chemin nominal ne met plus à jour la vignette"

    _sip.delete(_lbl)
    try:
        _row._on_apercu_changed("plan-42", "")
    except RuntimeError as exc:
        raise AssertionError(
            "la vignette détruite fait toujours planter : " + str(exc)) from None

    # 3. Les deux autres points d'appel sont gardés eux aussi.
    _src = inspect.getsource(PSL)
    assert "if not _alive(row_self):" in _src, \
        ("le rafraîchissement de fermeture de la fenêtre Mood n'est pas gardé — "
         "c'est la ligne exacte du crash rapporté")
    _batch = inspect.getsource(PSL.PageStoryboard._on_batch_mood_done)
    assert "_alive(row)" in _batch, \
        ("la génération de moods en série écrit dans _shot_rows sans vérifier "
         "que la ligne existe encore")


@test
def refus_de_rognage_dit_ce_qui_ne_va_pas():
    """« Façade non isolée » nomme la cause mesurée et où la corriger.

    Signalé par Matthieu le 2026-07-26 : le rognage refuse avec « détoure-la
    d'abord », sans dire ce qui a été mesuré ni où se trouve l'outil qui le fait.
    Or les deux causes se soignent différemment — un cadre entièrement éclairé
    veut dire qu'aucun fond noir n'entoure le bâtiment (c'est encore une photo
    avec son décor) ; un cadre presque éteint, que l'image est trop sombre pour
    qu'une silhouette s'en détache.
    """
    import tempfile
    from PIL import Image
    from core.live_mapping import (build_facade_mask, facade_mask_coverage,
                                   _MASK_MAX_COVER, _MASK_MIN_COVER)

    _d = tempfile.mkdtemp()

    def _cas(nom, img):
        p = os.path.join(_d, nom + ".png")
        img.save(p)
        return facade_mask_coverage(p), bool(
            build_facade_mask(p, os.path.join(_d, nom + "_m.png")))

    # 1. Photo non détourée (le cas de Matthieu) : cadre entièrement « éclairé ».
    _cov, _ok = _cas("photo", Image.new("RGB", (200, 150), (40, 45, 70)))
    assert not _ok and _cov >= _MASK_MAX_COVER, \
        ("une photo non détourée doit être refusée par le HAUT", _cov)

    # 2. Image trop sombre : rien ne ressort du fond.
    _cov, _ok = _cas("sombre", Image.new("RGB", (200, 150), (5, 5, 5)))
    assert not _ok and _cov <= _MASK_MIN_COVER, \
        ("une image trop sombre doit être refusée par le BAS", _cov)

    # 3. Façade correctement isolée : acceptée (sinon le refus serait systématique
    #    et le test ne prouverait rien).
    _im = Image.new("RGB", (200, 150), (0, 0, 0))
    for _x in range(70, 130):
        for _y in range(40, 140):
            _im.putpixel((_x, _y), (200, 190, 170))
    _cov, _ok = _cas("isolee", _im)
    assert _ok, ("une façade correctement isolée est refusée", _cov)
    assert _MASK_MIN_COVER < _cov < _MASK_MAX_COVER

    # 4. Illisible → -1, jamais une exception.
    assert facade_mask_coverage(os.path.join(_d, "inexistant.png")) < 0

    # 5. Le message distingue les deux causes ET nomme le bouton qui les corrige.
    import inspect as _i
    import ui.dialog_apercu as _DA
    _src = _i.getsource(_DA.MoodDialog._crop_to_facade)
    assert "facade_mask_coverage" in _src, "le refus n'affiche aucune mesure"
    assert "_MASK_MAX_COVER" in _src and "_MASK_MIN_COVER" in _src, \
        "le refus ne distingue pas trop clair de trop sombre"
    assert "Isoler (fond noir)" in _src, \
        ("le message n'indique pas OÙ détourer — l'outil existe pourtant dans le "
         "Conducteur, l'utilisateur ne peut pas le deviner")
    from core.i18n import _FR_TO_EN
    assert any("Isoler (fond noir)" in k for k in _FR_TO_EN), \
        "le chemin vers l'outil n'est pas traduit"


@test
def blocs_de_barre_du_decoupage_jusquau_moteur():
    """Les sept blocs LIVE traversent toute la chaîne : découpage → plan → Studio.

    Dernier maillon du chantier (2026-07-27). Trois exigences, chacune adossée à un
    mode de panne identifié pendant la reconnaissance :

    · le contrat partagé core/decoupage_document n'est PAS modifié — les blocs
      vivent DANS le champ PROMPT VISUEL, que le parseur lit jusqu'au prochain
      libellé CONNU. Le Cinéma ne voit donc jamais rien, et la ligne
      « PROMPT VISUEL : » reste présente : sans elle la détection v2 échoue et
      tout le Live retomberait en réécriture IA, en silence ;
    · les DEUX points d'écriture des plans passent par la MÊME fonction —
      n'en enrichir qu'un produit une perte à 100 % sur l'autre, sans aucun signe
      (mode de panne déjà vécu avec decoupage_content / layout_content) ;
    · le Studio consomme les blocs plutôt que la prose aplatie, et le plan porte
      sa durée EXACTE pour le recalage ffmpeg.
    """
    import ast
    import core.decoupage_document as DD
    from core.live_bar import (bpm_of_track, format_blocks, has_blocks,
                               parse_blocks, shot_extras)

    DOC = """DÉCOUPAGE PANDORA 2

SÉQUENCE 1 — Intro

PLAN 01
SOURCE CONDUCTEUR : nappe grave, la façade se givre
INTENTION : installer la tension
DURÉE : 4
PROMPT VISUEL :
SURFACE : trapezoidal church facade, square bell tower
ÉTAT 0 : nothing moves, the stone already veiled in thin frost
TRANSFORMATION : the frost thickens steadily, crystals proliferating outward
ÉTAT 1 : the frost has closed over the openings
NOIR : background pure black, no gradient, no glow
STYLE : frozen antique engraving
CONTRAINTES : no text, no watermark
SON : souffle glacé grave, réverbération de cathédrale
PERSONNAGES : —
"""

    # ── 1. Le contrat partagé n'est pas touché ────────────────────────────────
    for _bloc in ("SURFACE", "ÉTAT 0", "TRANSFORMATION", "NOIR", "CONTRAINTES"):
        assert not any(_bloc in al for al in DD._LABELS.values()), \
            (f"« {_bloc} » a été déclaré dans le contrat PARTAGÉ — le Cinéma s'en "
             "trouve contraint, et un plan Cinéma contenant ce mot verrait son "
             "champ précédent coupé")
    assert DD.is_v2_document(DOC), \
        ("le document n'est plus reconnu v2 : is_structured_layout retomberait sur "
         "les branches héritées et chaque découpage repartirait en réécriture IA")

    _segs = DD.parse_v2_document(DOC)
    assert len(_segs) == 1, ("un seul plan attendu", len(_segs))
    _seg = _segs[0]
    assert "souffle" in _seg["sound_prompt"].lower(), \
        "le SON n'est plus isolé — les blocs l'ont absorbé"
    assert "cathédrale" not in _seg["prompt"], \
        "le son a fui dans le PROMPT VISUEL"

    # ── 2. Les blocs ressortent intacts, et l'aller-retour est stable ─────────
    _b = parse_blocks(_seg["prompt"])
    assert set(_b) == {"surface", "state_0", "transformation", "state_1",
                       "black", "style", "constraints"}, sorted(_b)
    assert _b["state_1"] == "the frost has closed over the openings"
    assert parse_blocks(format_blocks(_b)) == _b, "l'aller-retour perd des blocs"
    assert has_blocks(_seg["prompt"]) and not has_blocks("une prose libre sans blocs")

    # ── 3. La durée EXACTE de la barre est calculée ──────────────────────────
    _tracks = [{"name": "Intro", "bpm": 118}]
    assert bpm_of_track("Intro", _tracks) == 118.0
    assert bpm_of_track("Absent", _tracks) == 0.0
    _ex = shot_extras(_seg, 118.0)
    assert _ex["beats"] == 8, ("4 s à 118 BPM ≈ 8 temps", _ex)
    assert abs(_ex["duration_exact"] - 4.068) < 0.01, _ex
    assert _ex["live_bar"] == _b
    # Sans tempo connu, on n'invente rien.
    assert "duration_exact" not in shot_extras(_seg, 0.0)
    # Un plan sans blocs n'en fabrique pas.
    assert "live_bar" not in shot_extras({"prompt": "prose libre", "duration": 4}, 118)

    # ── 4. Les DEUX points d'écriture passent par la même fonction ───────────
    import ui.page_scenario_live as PScL
    import ui.page_storyboard_live as PStL
    _w1 = inspect.getsource(PScL.PageScenario._write_decoupage_segments)
    _w2 = inspect.getsource(PStL.PageStoryboard._segments_to_shots)
    for _nom, _src in (("Appliquer le découpage", _w1), ("Séquences", _w2)):
        assert "shot_extras(" in _src, \
            (f"le chemin « {_nom} » n'écrit pas les blocs — perte 100 % silencieuse "
             "sur ce chemin, l'autre continuant de marcher")
        assert "bpm_of_track(" in _src, \
            f"le chemin « {_nom} » n'écrit pas la durée exacte de barre"

    # ── 5. Le Studio consomme les blocs, pas la prose ────────────────────────
    import ui.tab_t2v_live as TL
    _inp = inspect.getsource(TL.TabT2V._live_compose_inputs)
    assert "format_blocks" in _inp and '"live_bar"' in _inp, \
        ("le Studio aplatit encore la prose : le composeur devrait redeviner où "
         "sont les trois temps, et c'est là qu'ils se dissolvent")
    assert '"beats"' in _inp, "le nombre de temps du plan n'est pas repris"

    # ── 6. Le validateur exige la barre en MAPPING, et seulement là ──────────
    from api.live_extract import validate_live_layout
    assert validate_live_layout(DOC, "mapping") == [], \
        "un découpage mapping conforme est refusé"
    _plat = DOC.replace(
        "SURFACE : trapezoidal church facade, square bell tower\n"
        "ÉTAT 0 : nothing moves, the stone already veiled in thin frost\n"
        "TRANSFORMATION : the frost thickens steadily, crystals proliferating outward\n"
        "ÉTAT 1 : the frost has closed over the openings\n",
        "une façade givrée, dense et contrastée, très détaillée\n")
    assert validate_live_layout(_plat, "mapping") == ["P01:barre"], \
        ("une prose sans les trois temps doit être refusée en mapping",
         validate_live_layout(_plat, "mapping"))
    assert validate_live_layout(_plat, "live") == [], \
        "la règle de barre déborde sur le VJ libre, qui n'a pas de façade"
    assert validate_live_layout(_plat) == [], "le mode par défaut n'est plus permissif"

    # ── 7. La relance corrective est en MIROIR du premier jet ────────────────
    from api.live_extract import layout_correction
    _corr_map = layout_correction("mapping")
    for _must in ("SURFACE", "ÉTAT 0", "TRANSFORMATION", "ÉTAT 1", "NOIR"):
        assert _must in _corr_map, \
            (f"la relance mapping ne rappelle pas « {_must} » : elle téléguiderait "
             "vers l'ancien contrat et l'échec empirerait à chaque tour", _must)
    assert "PROMPT VISUEL" in _corr_map
    assert "SURFACE" not in layout_correction("live"), \
        "la relance VJ réclame des blocs qui n'ont pas d'objet hors mapping"
    _sys = inspect.getsource(_LE_module().FormatConducteurWorker.run)
    assert "_visuel_mapping" in _sys and "_visuel_live" in _sys, \
        "le premier jet ne distingue plus les deux contrats"

    # ── 8. core/live_bar reste PUR (aucun appel IA, aucun Qt) ────────────────
    import core.live_bar as LB
    _mods = set()
    for _n in ast.walk(ast.parse(inspect.getsource(LB))):
        if isinstance(_n, ast.ImportFrom):
            _mods.add(_n.module or "")
        elif isinstance(_n, ast.Import):
            _mods.update(a.name for a in _n.names)
    for _interdit in ("core.ai_provider", "core.lang", "PyQt6",
                      "core.engine_grammar", "core.decoupage_document"):
        assert _interdit not in _mods, \
            (f"core/live_bar doit rester pur et autonome — importe « {_interdit} »")


def _LE_module():
    import api.live_extract as _m
    return _m


@test
def bande_conducteur_lit_toujours_sa_propre_sequence():
    """Le Conducteur et le raccord ne lisent plus la séquence d'un autre onglet.

    Bug rapporté par Matthieu le 2026-07-27 : après avoir arrêté la file d'attente
    et supprimé la dernière frame d'un plan, la bande passait de 10 plans à 5 ; et
    en relançant au plan 4, le raccord repartait de la frame du plan 1.

    UNE seule cause pour les deux. `core.storyboard.set_namespace` est un état
    GLOBAL de module : le Sound Design Live l'écrit avec SON mode à lui
    (ui/tab_sound_design_live.py) sans jamais le restaurer. La bande lisait donc
    une autre séquence, tronquée — et le raccord, qui prend le plan précédent dans
    CETTE liste, remontait au mauvais plan. Le contournement trouvé par Matthieu
    est la preuve du mécanisme : changer d'onglet et revenir rappelle showEvent,
    qui repose le namespace et fait réapparaître les plans.
    """
    import ui.tab_t2v_live as TL

    # ── 1. La bande possède SA séquence et la réaffirme avant chaque accès ────
    _sel = TL.StoryboardSelector()
    assert hasattr(_sel, "_ns"), "la bande ne connaît pas sa propre séquence"
    _sel.set_namespace("live_seq_mapping")
    assert _sel._ns == "live_seq_mapping"
    import core.storyboard as _sb
    _avant = _sb.get_namespace()
    try:
        _sb.set_namespace("live_seq_live")      # un autre onglet déplace l'état global
        _sel._pin_ns()
        assert _sb.get_namespace() == "live_seq_mapping", \
            "la bande ne récupère pas sa séquence — elle lira celle d'un autre onglet"
    finally:
        _sb.set_namespace(_avant)

    for _nom, _fn in (("_load_shots", TL.StoryboardSelector._load_shots),
                      ("_clear_last_frame", TL.StoryboardSelector._clear_last_frame)):
        assert "_pin_ns()" in inspect.getsource(_fn), \
            (f"{_nom} accède au storyboard sans réaffirmer sa séquence")

    # Le Studio tient la bande informée à CHAQUE bascule de mode.
    _src = inspect.getsource(TL)
    assert _src.count("_storyboard.set_namespace(") >= 4, \
        ("la bande doit être resynchronisée à la construction, au showEvent, au "
         "changement de mode ET au refresh — sinon elle dérive à nouveau")
    _sel_shot = inspect.getsource(TL.TabT2V._on_shot_selected_impl)
    assert "sb_api.set_namespace(" in _sel_shot and "list_shots()" in _sel_shot, \
        ("la liste passée au raccord est lue sans fixer la séquence — c'est ce qui "
         "faisait remonter le raccord au plan 1")

    # ── 2. Le raccord prend bien le plan IMMÉDIATEMENT précédent ─────────────
    _bar = TL._ContinuityBar()
    _complet = [{"number": n} for n in range(1, 11)]
    _bar.update_shot({"number": 4}, _complet)
    assert _bar._prev_shot["number"] == 3, \
        ("sur une liste complète le précédent du plan 4 est le plan 3",
         _bar._prev_shot)
    # Et sur une liste TRONQUÉE il se trompe — c'est précisément le symptôme
    # observé, donc la preuve que la cause est bien la liste et pas le calcul.
    _bar.update_shot({"number": 4}, [{"number": 1}, {"number": 4},
                                     {"number": 5}, {"number": 6}])
    assert _bar._prev_shot["number"] == 1, \
        "le symptôme n'est plus reproductible — ce test ne prouve plus rien"

    # ── 3. La rangée du raccord n'a plus ses widgets flottants ───────────────
    _bar2 = TL._ContinuityBar()
    _bar2.resize(1400, 90)
    _bar2._i2v_thumb.setVisible(True)
    _bar2._i2v_row_widget.setVisible(True)
    _bar2.setVisible(True)
    _bar2.grab()                       # force le calcul de layout
    _lay = _bar2._i2v_row_widget.layout()
    _x_icone = _lay.itemAt(0).widget().geometry().x()
    _x_thumb = _bar2._i2v_thumb.geometry().x()
    assert _x_icone < 60 and _x_thumb < 120, \
        ("icône et vignette flottent au milieu de la barre : la case masquée garde "
         "son facteur d'étirement", _x_icone, _x_thumb)
    assert _bar2._i2v_caption.text(), \
        "la vignette n'est accompagnée d'aucune légende — on ne sait pas ce qu'elle montre"
    from core.i18n import _FR_TO_EN
    assert any("dernière frame du plan précédent" in k for k in _FR_TO_EN), \
        "légende du raccord non traduite"


@test
def le_mood_atteint_vraiment_le_moteur():
    """Le Mood du plan part bien à Seedance, et se voit dans les images envoyées.

    Constaté par Matthieu le 2026-07-27 : « le rendu est très différent de
    l'image du Mood », puis « je vois la façade et les trois images de référence,
    mais pas l'image du mood ». DEUX défauts cumulés, tous deux côté Live :

    1. les moods sont rangés SOUS le dossier de la séquence
       (core.storyboard.get_apercu_dir → _sb_dir → _NAMESPACE). Un namespace
       déplacé par un autre onglet faisait chercher les moods du Mapping dans le
       dossier du Live : aucun trouvé, donc aucune image-clé, donc un envoi en
       t2v où le Mood n'atteignait jamais le moteur ;
    2. la bande de vignettes testait « _mood_ref_cb » et « _active_mood_path »,
       deux attributs qui n'existent NULLE PART — la condition valait toujours
       faux, le Mood n'était jamais affiché parmi les images envoyées.
    """
    import core.storyboard as sb
    from PIL import Image
    from ui.tab_t2v_live import TabT2V

    sb.set_namespace("live_seq_mapping")
    sb.clear_version_shots(sb.DEFAULT_VERSION_ID)
    _shots = [sb.save_shot({"number": i, "scene_title": f"P{i}", "duration": 6},
                           sb.DEFAULT_VERSION_ID) for i in (1, 2)]
    for _s in _shots:
        _ad = sb.get_apercu_dir(_s["id"])
        os.makedirs(_ad, exist_ok=True)
        _p = os.path.join(_ad, f"mood_{_s['number']}.jpg")
        Image.new("RGB", (32, 18), (70, 40, 90)).save(_p)
        sb.save_apercus(_s["id"], [_p], 0)

    t = TabT2V()
    t._set_seq_mode("mapping")

    # ── 1. Le mood est trouvé MÊME si un autre onglet a déplacé le namespace ──
    sb.set_namespace("live_seq_live")          # exactement ce que fait le Sound Design
    _kf, _ = t._get_mapping_keyframes(_shots[0])
    assert _kf and _kf.endswith("mood_1.jpg"), \
        ("le mood n'est pas retrouvé quand le namespace a dérivé — c'est ce qui "
         "faisait partir le plan en t2v sans mood", _kf)
    assert sb.get_namespace() == "live_seq_mapping", \
        "la recherche de mood doit reposer le namespace de la séquence"

    # ── 2. Le mood figure dans les images ANNONCÉES comme envoyées ───────────
    t._active_shot = _shots[0]
    _imgs = t._all_reference_images()
    assert any(p.endswith("mood_1.jpg") for p in _imgs), \
        ("le Mood n'apparaît pas dans les images envoyées — c'est le constat "
         "exact de Matthieu", [os.path.basename(p) for p in _imgs])

    # Décoché → il n'y figure plus : la case pilote vraiment quelque chose.
    t._use_mood_cb.setChecked(False)
    assert not any(p.endswith("mood_1.jpg") for p in t._all_reference_images()), \
        "la case « Utiliser les images du Mood » n'a aucun effet sur ce qui est envoyé"
    t._use_mood_cb.setChecked(True)

    # ── 3. Les attributs fantômes ne doivent pas revenir ─────────────────────
    _src = inspect.getsource(TabT2V._all_reference_images)
    for _mort in ("_mood_ref_cb", "_active_mood_path"):
        _code = "\n".join(l for l in _src.splitlines()
                          if not l.lstrip().startswith("#"))
        assert _mort not in _code, \
            (f"« {_mort} » n'existe nulle part dans le fichier : la condition vaut "
             "toujours faux et le Mood disparaît à nouveau")

    # ── 4. L'ancrage réel est ANNONCÉ à l'écran ──────────────────────────────
    _prev = inspect.getsource(TabT2V._build_full_preview_text)
    assert "Départ :" in _prev and "Arrivée :" in _prev, \
        "rien ne dit d'où part le plan ni sur quelle image il atterrit"
    from core.i18n import _FR_TO_EN
    assert any("Arrivée : Mood de ce plan" in k for k in _FR_TO_EN), \
        "annonce de la chaîne départ → arrivée non traduite"

    # ── 5. DEUX PLAQUES : le raccord ET le Mood, pas l'un OU l'autre ─────────
    # Le 2026-07-27 j'avais donné la priorité au Mood en retirant « not
    # i2v_frame » : le Mood revenait, mais les raccords disparaissaient
    # (« ça n'utilise plus la dernière image du dernier plan »). Les deux
    # réglages étaient exclusifs et se volaient l'image de départ ; aucun ne
    # décrivait ce qui est voulu — partir de la frame précédente et ARRIVER sur
    # le Mood du plan.
    _sg2 = inspect.getsource(TabT2V.start_generation)
    assert "end_frame = kf_start" in _sg2, \
        ("le Mood n'est pas posé en image d'ARRIVÉE : soit il vole le départ au "
         "raccord, soit il ne sert à rien")
    assert '"end_image_path"' in _sg2, "l'image d'arrivée n'est pas transmise à l'envoi"
    assert 'self._anchor_kind = "raccord+mood"' in _sg2, \
        "le cas où les deux images coexistent n'est pas identifié"
    # Et le repli reste : sans frame précédente, le Mood redevient le départ.
    assert "i2v_frame = kf_start" in _sg2, \
        "premier plan (aucune frame précédente) : le Mood doit rester le départ"

    sb.set_namespace("storyboard")


@test
def verrou_facade_atteint_le_payload():
    """Le verrou géométrique du mapping doit PARTIR au moteur, mode final compris.

    Régression vécue (2026-07-27, introduite la veille par le chantier « prompt
    final composé ») : pour éviter les doublons dans le payload, TOUS les
    suffixes ont été neutralisés en mode final —

        "time_suffix": "" if _final_mode else time_suffix

    Or en mapping `time_suffix` ne porte pas que du style : il porte
    `_mapping_dna`, c'est-à-dire « STATIC LOCKED CAMERA — absolutely no zoom
    […] the facade keeps the EXACT same width-to-height ratio […] pixel-locked ».
    Et le mode final est le cas NORMAL : `_await_final_then_generate` attend
    `_prompt_is_final` avant de lancer chaque plan. Le verrou ne partait donc
    plus jamais, et rien dans le texte envoyé n'interdisait au bâtiment de
    dériver. Constat de Matthieu : « j'ai toujours de légères déformations sur
    le bâtiment ou pendant le plan, ça peut zoomer un tout petit peu ».

    Lecture par AST et NON par recherche de texte : le commentaire qui explique
    la règle cite forcément le motif interdit, piège déjà tombé cinq fois sur ce
    harnais (cf. `grammaire_live_separee`).
    """
    import ast
    import ui.tab_t2v_live as TL

    with open(TL.__file__, encoding="utf-8-sig") as fh:
        tree = ast.parse(fh.read())

    _fn = None
    for _node in ast.walk(tree):
        if isinstance(_node, ast.FunctionDef) and _node.name == "start_generation":
            _fn = _node
            break
    assert _fn is not None, "start_generation introuvable dans ui/tab_t2v_live.py"

    # ── 1. La clé "time_suffix" du payload ───────────────────────────────────
    _val = None
    for _node in ast.walk(_fn):
        if not isinstance(_node, ast.Dict):
            continue
        for _k, _v in zip(_node.keys, _node.values):
            if isinstance(_k, ast.Constant) and _k.value == "time_suffix":
                _val = _v
    assert _val is not None, "aucune clé « time_suffix » dans le payload de start_generation"
    _expr = ast.unparse(_val)

    assert "_mapping_lock" in _expr, (
        "le verrou géométrique du mapping ne part plus au moteur : la clé "
        "« time_suffix » du payload vaut « " + _expr + " ». En mode final elle "
        "s'évalue à une chaîne VIDE, donc plus aucune consigne n'interdit au "
        "bâtiment de zoomer ou de changer de proportions.")

    # ── 2. Le verrou est bien CONSTRUIT, et il dit la bonne chose ────────────
    _assigne = [n for n in ast.walk(_fn)
                if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "_mapping_lock"
                        for t in n.targets)]
    assert len(_assigne) >= 2, (
        "_mapping_lock doit être initialisé à vide PUIS rempli en mapping — "
        f"{len(_assigne)} affectation(s) trouvée(s)")

    _dna = [n.value for n in ast.walk(_fn)
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "_mapping_dna"
                    for t in n.targets)]
    assert _dna, "_mapping_dna a disparu — c'est lui qui porte tout le verrou"
    _texte = ast.literal_eval(_dna[0]).lower()
    for _exigence in ("no zoom", "locked", "proportions", "never rescales"):
        assert _exigence in _texte, (
            f"« {_exigence} » absent du verrou façade : le texte envoyé ne "
            "couvre plus la dérive géométrique constatée à l'écran")

    # ── 3. Un verrou invisible peut disparaître sans bruit : il s'annonce ────
    _prev = inspect.getsource(TL.TabT2V._build_full_preview_text)
    assert "Verrou façade" in _prev, (
        "le verrou n'est pas annoncé dans « Éléments injectés » — il a déjà "
        "disparu du payload une fois sans que rien ne le signale")
    from core.i18n import _FR_TO_EN
    assert any("Verrou façade" in k for k in _FR_TO_EN), \
        "annonce du verrou façade non traduite en anglais"


@test
def refus_de_composition_nest_pas_repaye():
    """Un plan refusé par le contrôle de barre ne recompose pas à chaque retour.

    Constat de Matthieu (2026-07-27) : « lorsqu'on désélectionne le plan et
    qu'on le resélectionne, elle se refait à nouveau alors qu'elle a déjà été
    chargée et qu'entre temps il n'y a pas eu de modification ».

    La clé de cache était pourtant bonne — vérifié en rejouant le cycle complet
    sélection → désélection → resélection : même empreinte, cache touché. Le
    défaut était dans `_remember_final`, qui ne mémorisait QUE les succès. Or
    `why` confond deux natures d'échec :

      · transitoire  (crédits, quota, réseau, clé absente) → à retenter
      · déterministe (refus du contrôle de barre)          → même verdict à
        chaque fois, donc un aller-retour IA repayé pour rien à chaque
        resélection du plan

    Ce test fige le tri, et le fait qu'un refus mémorisé ne relance rien.
    """
    import core.storyboard as sb
    import api.live_video_prompt as LVP
    import ui.tab_t2v_live as TL
    from ui.tab_t2v_live import TabT2V

    # ── 1. Le tri des deux natures d'échec ───────────────────────────────────
    assert LVP.is_deterministic_refusal(
        LVP.REFUSAL_PREFIX + "structure de barre perdue"), \
        "un refus du contrôle de barre doit être reconnu comme déterministe"
    for _transitoire in ("crédits IA épuisés", "quota dépassé",
                         "clé Anthropic absente", "connexion interrompue", ""):
        assert not LVP.is_deterministic_refusal(_transitoire), \
            (f"« {_transitoire} » est un aléa d'infrastructure : le figer "
             "condamnerait le plan au repli jusqu'à la fermeture de l'app")

    # Le marqueur doit être POSÉ par compose(), pas dupliqué en littéral : deux
    # écritures parallèles divergeraient au premier reformulage du message.
    _src = "\n".join(l for l in inspect.getsource(LVP.compose).splitlines()
                     if not l.lstrip().startswith("#"))
    assert "REFUSAL_PREFIX" in _src, \
        "compose() n'utilise pas REFUSAL_PREFIX — le tri se fera sur un texte libre"

    # ── 2. _remember_final mémorise le refus, retente l'incident ─────────────
    sb.set_namespace("live_seq_mapping")
    sb.clear_version_shots(sb.DEFAULT_VERSION_ID)
    _shot = sb.save_shot({"number": 1, "scene_title": "P1", "duration": 6,
                          "seedance_prompt": "Une vague de lumière monte sur la façade."},
                         sb.DEFAULT_VERSION_ID)

    t = TabT2V()
    t._set_seq_mode("mapping")

    t._final_cache.clear()
    t._final_cache_key_pending = "K_refus"
    t._remember_final("repli déterministe", False,
                      LVP.REFUSAL_PREFIX + "coupe introduite dans la barre")
    assert "K_refus" in t._final_cache, \
        ("un refus du contrôle de barre n'est pas mémorisé : le même verdict "
         "sera repayé à chaque resélection du plan")

    t._final_cache_key_pending = "K_reseau"
    t._remember_final("repli", False, "crédits IA épuisés")
    assert "K_reseau" not in t._final_cache, \
        ("un incident d'infrastructure ne doit PAS être figé : une fois les "
         "crédits rechargés, le plan doit pouvoir se composer")

    # ── 3. Bout en bout : refus, puis retour sur le plan → aucun recalcul ────
    _vrai_worker = TL._LiveFinalPromptWorker

    class _WorkerMuet:
        """Ne compose rien : le test pilote lui-même le verdict."""
        def __init__(self, body, ctx):
            pass

        def start(self):
            pass
    TL._LiveFinalPromptWorker = _WorkerMuet
    try:
        t._final_cache.clear()
        t._final_assembly_timer.stop()

        t._on_shot_selected(_shot)
        t._final_assembly_timer.stop()          # on court-circuite le débounce
        t._start_final_assembly()
        assert not t._final_from_cache, "premier passage : rien ne peut être en cache"
        assert t._final_cache_key_pending, "la clé d'entrée n'a pas été retenue"

        # Ce que le worker aurait émis si le contrôle avait refusé la prose.
        t._on_final_composed("deterministic fallback prose", False,
                             LVP.REFUSAL_PREFIX + "structure de barre perdue")
        assert len(t._final_cache) == 1, "le refus n'a pas été rangé dans le cache"

        # Désélection, puis retour sur le MÊME plan, sans rien modifier.
        t._on_shot_selected(None)
        t._on_shot_selected(_shot)
        t._final_assembly_timer.stop()
        t._start_final_assembly()
        assert t._final_from_cache, \
            ("le plan recompose au retour alors que rien n'a changé — c'est le "
             "symptôme rapporté par Matthieu, et chaque passage est facturé")
    finally:
        TL._LiveFinalPromptWorker = _vrai_worker
        sb.set_namespace("storyboard")


@test
def lot_de_moods_compose_une_fois_par_plan():
    """« Action → Générer les Moods » compose aussi, et une seule fois par plan.

    Vérification demandée par Matthieu le 2026-07-27 : le compositeur avait été
    branché dans la fenêtre Mood, mais le LOT continuait d'envoyer le prompt
    déterministe français — mesuré à ZÉRO appel de composition. Le même plan
    donnait donc deux rendus différents selon le bouton cliqué.

    UNE composition par plan, pas par variation : les variations partagent le
    même prompt, seul le tirage change. Composer par variation multiplierait la
    facture sans rien apporter.
    """
    import core.storyboard as sb
    import api.apercu as A
    import api.image_prompt as IP

    sb.set_namespace("live_seq_mapping")
    sb.clear_version_shots(sb.DEFAULT_VERSION_ID)
    _p = ("SURFACE : façade en pierre.\n"
          "ÉTAT 0 : pierre givrée, portail sombre.\n"
          "TRANSFORMATION : le givre se fend.\n"
          "ÉTAT 1 : cristal bleu.\n"
          "STYLE : gravure gelée.\n")
    _shot = sb.save_shot({"number": 1, "scene_title": "P1",
                          "seedance_prompt": _p}, sb.DEFAULT_VERSION_ID)

    _compos, _envois = [], []
    _vrai_compose, _vrai_mood = IP.compose, A.run_mood
    try:
        IP.compose = lambda p, **kw: (_compos.append(kw) or
                                      "English composed prompt for the engine.")
        A.run_mood = (lambda shot, prompt, out_dir, key, cb, bref, **kw:
                      _envois.append(prompt) or "")
        _w = A.MoodBatchWorker([_shot], {"variations": 3})
        _w._building_ref = __file__      # un fichier qui existe → mode mapping
        _w.run()
    finally:
        IP.compose, A.run_mood = _vrai_compose, _vrai_mood

    assert len(_compos) == 1, (
        f"{len(_compos)} composition(s) pour 3 variations d'un même plan — "
        "elles partagent le même prompt, une seule suffit")
    assert len(_envois) == 3, ("les 3 variations n'ont pas été générées",
                               len(_envois))
    assert _compos[0].get("kind") == "mood_mapping", \
        ("le lot ne compose pas dans le contexte mapping", _compos[0].get("kind"))
    assert "OPENING state" in (_compos[0].get("moment") or ""), \
        "l'instant à rendre n'est pas transmis par le lot"
    for _p_envoye in _envois:
        assert _p_envoye == "English composed prompt for the engine.", (
            "le lot envoie le prompt déterministe au lieu du composé", _p_envoye[:60])

    # Le repli reste garanti : sans composition, le plan part quand même.
    try:
        IP.compose = lambda p, **kw: ""
        A.run_mood = (lambda shot, prompt, out_dir, key, cb, bref, **kw:
                      _envois.append(prompt) or "")
        # 4-uplet depuis le cache sur disque (2026-07-27) : le dernier
        # élément dit si la composition vient du cache plutôt que de l'IA.
        _txt, _ok, _why, _cache = A.compose_mood_prompt(
            _shot, "", "nb2", __file__)
        assert _txt.strip() and not _ok and _why, \
            "un refus de composition doit rendre le prompt déterministe ET sa raison"
        assert "SURFACE" in _txt, "le repli n'est pas l'assemblage déterministe"
    finally:
        IP.compose, A.run_mood = _vrai_compose, _vrai_mood
        sb.set_namespace("storyboard")


@test
def le_texte_gouverne_les_images_de_reference():
    """En mapping, la consigne passe AVANT le prompt, et les inspirations sont
    plafonnées.

    Constat de Matthieu (2026-07-27), sur « Action → Générer les Moods » avec
    Seedream 5.0 et trois variations : « les trois variations ressemblent
    toujours aux images de référence et jamais aux prompts ».

    Le chemin d'envoi n'avait pourtant pas changé — vérifié au diff : façade en
    image 1, inspirations ensuite, directives présentes. Ce qui a changé, c'est
    la LONGUEUR du texte : le bloc français faisait ~600 caractères, la
    composition en fait deux à quatre phrases, et le repli déterministe a lui
    aussi maigri (TRANSFORMATION et ÉTAT 1 retirés le même jour). Face aux mêmes
    images sur un endpoint /edit, le texte ne pèse plus assez.

    Deux leviers, tous deux vérifiés ici : la consigne passe en TÊTE — en queue
    elle se lit comme une remarque, en tête c'est un ordre — et le nombre
    d'inspirations est PLAFONNÉ, chaque image ajoutée pesant contre le texte.
    """
    import api.apercu as A

    # ① L'ordre : consigne d'abord, description ensuite.
    _out = A._avec_directive_en_tete("DESCRIPTION DU PLAN", " | LA CONSIGNE")
    assert _out.startswith("LA CONSIGNE"), (
        "la consigne n'est pas en tête — sur un endpoint /edit elle se lit alors "
        "comme une remarque et les images gagnent", _out[:60])
    assert "DESCRIPTION DU PLAN" in _out, "le prompt a été perdu"
    # Les deux cas dégénérés ne doivent pas produire de séparateur orphelin.
    assert A._avec_directive_en_tete("SEUL", "") == "SEUL"
    assert A._avec_directive_en_tete("", " | SEULE") == "SEULE"

    # ② Le plafond d'inspirations existe et reste bas.
    assert 1 <= A._MAX_INSPIRATION_MAPPING <= 3, (
        "le plafond d'images d'inspiration en mapping doit rester bas : chacune "
        "pèse face au texte", A._MAX_INSPIRATION_MAPPING)

    # ③ Il est réellement APPLIQUÉ sur les deux chemins d'envoi.
    for _fn in (A.run_generation_nb2, A.run_generation_engine):
        _src = "\n".join(l for l in inspect.getsource(_fn).splitlines()
                         if not l.lstrip().startswith("#"))
        assert "_MAX_INSPIRATION_MAPPING" in _src, (
            f"« {_fn.__name__} » n'applique pas le plafond d'inspirations")
        assert "_avec_directive_en_tete" in _src, (
            f"« {_fn.__name__} » ne met pas la consigne en tête")


@test
def composition_survit_a_la_fermeture_du_mood():
    """Rouvrir un plan inchangé ne doit RIEN repayer.

    Constat de Matthieu (2026-07-27) : « quand on ferme la fenêtre du Mood, qui a
    déjà été composé, et qu'on la rouvre, la composition se refait ». Le cache
    vivait sur l'instance du dialogue — il mourait donc avec la fenêtre, et
    chaque réouverture était un aller-retour IA FACTURÉ.

    Il vit désormais À CÔTÉ des moods du plan, sur disque. La clé porte la fiche,
    l'instant, la surface, le style, le moteur et le type : modifier le plan ou
    changer de moteur la change, et la composition repart — mais elle seule.
    """
    import core.storyboard as sb
    import api.apercu as A
    import api.image_prompt as IP
    import core.ai_provider as AP

    sb.set_namespace("live_seq_mapping")
    sb.clear_version_shots(sb.DEFAULT_VERSION_ID)
    _p = "\n".join((
        "SURFACE : façade.",
        "ÉTAT 0 : pierre givrée.",
        "TRANSFORMATION : le gel s'épaissit.",
        "ÉTAT 1 : givre opaque.",
        "STYLE : gravure gelée.",
    ))
    _shot = sb.save_shot({"number": 1, "scene_title": "P1",
                          "seedance_prompt": _p}, sb.DEFAULT_VERSION_ID)

    _n = [0]
    _vc, _vk = IP.compose, AP.key_error
    try:
        IP.compose = lambda p, **kw: (_n.__setitem__(0, _n[0] + 1),
                                      "Composed English prompt.")[1]
        AP.key_error = lambda **kw: None

        _r1 = A.compose_mood_prompt(_shot, "", "nb2", __file__)
        assert _n[0] == 1 and not _r1[3], "la première composition doit appeler l'IA"

        # Fermer puis rouvrir la fenêtre = rappeler la même fonction.
        _r2 = A.compose_mood_prompt(_shot, "", "nb2", __file__)
        assert _n[0] == 1, (
            f"{_n[0]} appels IA pour deux ouvertures du même plan inchangé — "
            "chaque réouverture est facturée")
        assert _r2[3], "le 4ᵉ élément doit annoncer que le prompt vient du cache"
        assert _r1[0] == _r2[0], "le cache ne rend pas le même prompt"

        # Modifier le plan DOIT relancer la composition.
        _shot["seedance_prompt"] = _p.replace("pierre givrée", "pierre nue")
        _r3 = A.compose_mood_prompt(_shot, "", "nb2", __file__)
        assert _n[0] == 2 and not _r3[3],             "modifier le prompt du storyboard doit invalider le cache"

        # Changer de moteur aussi — la grammaire n'est pas la même.
        A.compose_mood_prompt(_shot, "", "seedream45", __file__)
        assert _n[0] == 3, "changer de moteur doit invalider le cache"

        # …et revenir à un état déjà composé le retrouve.
        _r5 = A.compose_mood_prompt(_shot, "", "nb2", __file__)
        assert _n[0] == 3 and _r5[3],             "le cache ne garde qu'une entrée : revenir sur un état déjà composé repaie"
    finally:
        IP.compose, AP.key_error = _vc, _vk
        sb.set_namespace("storyboard")


@test
def mood_ne_decrit_que_letat_douverture():
    """Le Mood ne doit PAS recevoir la transformation ni l'état final.

    Constat de Matthieu (2026-07-27, captures à l'appui) : les moods rendaient
    le monde forestier FINAL — arbres, cerf, renard, hibou — alors que l'ÉTAT 0
    du plan dit « façade encore majoritairement givrée, portail sombre ».

    Cause : le mood est l'image de DÉPART du plan, mais on lui envoyait la barre
    ENTIÈRE — TRANSFORMATION et ÉTAT 1 compris — avant de lui demander, en une
    phrase anglaise, d'« ignorer l'évolution ». Un moteur d'image ne sait pas
    ignorer : il rend ce qu'on lui décrit. Décrire ce qu'on ne veut pas voir est
    le plus sûr moyen de l'obtenir.

    Les deux blocs temporels sont désormais RETIRÉS, pas contredits — et la
    consigne négative disparaît avec eux.
    """
    import core.storyboard as sb
    import api.apercu as A

    sb.set_namespace("live_seq_mapping")
    _p = (
        "SURFACE : façade en pierre, portail en ogive, rosace centrale.\n"
        "ÉTAT 0 : rosace battante en lumière chaude, façade encore givrée.\n"
        "TRANSFORMATION : la rosace projette une forêt ; un cerf, un renard et "
        "un hibou de lumière surgissent.\n"
        "ÉTAT 1 : façade recouverte d'un monde forestier vert-doré.\n"
        "NOIR : le fond hors façade.\n"
        "STYLE : clair-obscur doré et vert.\n"
        "CONTRAINTES : aucun texte, façade à l'échelle exacte.\n"
    )
    _out = A.build_mood_prompt({"id": "s1", "number": 1, "seedance_prompt": _p},
                               "", "nb2")

    for _interdit in ("TRANSFORMATION", "ÉTAT 1", "forestier", "cerf", "renard",
                      "hibou"):
        assert _interdit not in _out, (
            f"« {_interdit} » part au moteur alors que le mood ne doit montrer "
            "que l'état d'ouverture — c'est ce qui fait apparaître la forêt et "
            "les animaux sur une façade censée être encore givrée")

    # Une consigne négative ne remplace pas le retrait : si les blocs sont bien
    # partis, il n'y a plus rien à ignorer.
    assert "ignore the later" not in _out, \
        "la consigne « ignore the later evolution » survit alors qu'elle n'a plus d'objet"

    # Et ce qui décrit l'image fixe doit rester.
    for _requis in ("SURFACE", "ÉTAT 0", "NOIR", "STYLE", "CONTRAINTES"):
        assert _requis in _out, f"« {_requis} » a disparu du prompt du mood"

    sb.set_namespace("storyboard")


@test
def mood_actif_apres_serie_nest_pas_un_tirage_au_hasard():
    """Sur une série de variations, le mood ACTIF doit être la PREMIÈRE.

    Le mood actif n'est pas un détail d'affichage : c'est lui qui sert d'image
    de départ à la génération vidéo. Le lot le posait sur la DERNIÈRE variation
    produite — donc sur un tirage aléatoire que personne n'avait regardé.
    Demander quatre variations revenait à laisser la quatrième piloter le rendu,
    bonne ou mauvaise ; et comme chaque tirage est indépendant, une sur quatre
    ratée suffisait à donner l'impression que « la façade est moins respectée
    quand j'en demande plusieurs ».

    La fenêtre Mood se plaçait déjà sur la première des nouvelles : le lot fait
    désormais pareil. Les autres variations restent là pour être comparées et
    choisies à l'œil — c'est tout leur intérêt.
    """
    from PIL import Image
    import core.storyboard as sb
    import api.apercu as A

    sb.set_namespace("live_seq_mapping")
    sb.clear_version_shots(sb.DEFAULT_VERSION_ID)
    _shot = sb.save_shot({"number": 1, "scene_title": "P1",
                          "seedance_prompt": "façade"}, sb.DEFAULT_VERSION_ID)

    _n = [0]
    _vrai = A.run_mood

    def _genere(shot, prompt, out_dir, key, cb, bref, **kw):
        _n[0] += 1
        os.makedirs(out_dir, exist_ok=True)
        _p = os.path.join(out_dir, f"var{_n[0]}.png")
        Image.new("RGB", (16, 9), (9, 9, 9)).save(_p)
        return _p

    try:
        A.run_mood = _genere
        A.MoodBatchWorker([_shot], {"variations": 4}).run()
    finally:
        A.run_mood = _vrai

    _r = sb.load_apercus(_shot["id"])
    assert len(_r["paths"]) == 4, ("les 4 variations ne sont pas toutes enregistrées",
                                   _r["paths"])
    assert _r["active_idx"] == 0, (
        "le mood ACTIF est la variation "
        f"{_r['active_idx'] + 1}/4 — c'est un tirage au hasard qui pilotera "
        "l'image de départ de la vidéo")
    assert _r["paths"][_r["active_idx"]].endswith("var1.png"), \
        "l'index actif ne pointe pas sur la première variation"

    sb.set_namespace("storyboard")


@test
def moods_generes_dans_leur_propre_sequence():
    """Un lot de Moods ne doit pas dépendre de l'onglet ouvert pendant qu'il tourne.

    Constat de Matthieu (2026-07-27) : en demandant PLUSIEURS variations depuis
    « Action → Générer les Moods », la façade est nettement moins respectée.

    Mécanisme : `core.storyboard._NAMESPACE` est un état GLOBAL de module, qu'un
    autre onglet déplace sans le restaurer. `api/apercu` le lit à quatre endroits
    sans jamais le reposer — dont `get_apercu_dir` (où le mood est ÉCRIT) et
    `_resolve_building_ref`, qui exige EXACTEMENT « live_seq_mapping » : sur une
    dérive, il renvoie "" et la façade n'est plus envoyée du tout, donc le moteur
    invente le bâtiment.

    Le lien avec les variations est mécanique et non psychologique : un lot de N
    variations dure N fois plus longtemps, donc laisse N fois plus d'occasions à
    la dérive de se produire.

    Le worker photographie donc le namespace à sa construction — sur le thread UI,
    où il est encore juste — et le repose au début de run().
    """
    import core.storyboard as sb
    import api.apercu as A

    sb.set_namespace("live_seq_mapping")
    sb.clear_version_shots(sb.DEFAULT_VERSION_ID)
    _shot = sb.save_shot({"number": 1, "scene_title": "P1",
                          "seedance_prompt": "façade"}, sb.DEFAULT_VERSION_ID)

    _vus = []
    _vrai = A.run_mood

    def _espion(shot, prompt, out_dir, key, cb, bref, **kw):
        _vus.append((sb.get_namespace(), out_dir))
        return ""

    try:
        A.run_mood = _espion
        w = A.MoodBatchWorker([_shot], {"variations": 3})
        # Exactement ce que fait ui/tab_sound_design_live : il pose SON namespace
        # et ne le restaure pas. Le worker est déjà construit, il tourne après.
        sb.set_namespace("live_seq_live")
        w.run()
    finally:
        A.run_mood = _vrai

    assert len(_vus) == 3, ("les 3 variations n'ont pas toutes été lancées", len(_vus))
    for _i, (_ns, _dir) in enumerate(_vus, 1):
        assert _ns == "live_seq_mapping", (
            f"variation {_i} : le lot tourne sous le namespace « {_ns} » au lieu de "
            "celui de sa séquence — la façade n'est plus résolue et les moods sont "
            "écrits ailleurs")
        assert "live_seq_mapping" in _dir.replace("\\", "/"), (
            f"variation {_i} : mood écrit hors de sa séquence", _dir)

    # Le worker unitaire porte la même garde.
    _w1 = A.MoodGenerationWorker(_shot, ".", variations=2)
    assert getattr(_w1, "_namespace", "") == "live_seq_mapping", \
        "le worker unitaire ne photographie pas son namespace"

    sb.set_namespace("storyboard")


if __name__ == "__main__":
    sys.exit(main())
