"""
tools/diff_live_cinema.py — Radar de divergence PANDORA Cinéma ↔ Live.

Le mécanisme « partager les bons changements sans contamination » : ce rapport
compare chaque paire de copies et liste, méthode par méthode, ce qui n'existe
que d'un côté et ce qui a divergé. C'est la LISTE DES CORRECTIFS/AMÉLIORATIONS
À REPORTER — à consulter en fin de session de travail sur l'un des deux côtés.

    C:\\Users\\22eme\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe tools\\diff_live_cinema.py

Aucune synchronisation automatique (protection volontaire) : l'outil INFORME,
l'humain décide quoi porter.
"""

import ast
import difflib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# (fichier Cinéma, copie Live)
PAIRS = [
    ("ui/tab_t2v.py",             "ui/tab_t2v_live.py"),
    ("ui/page_scenario.py",       "ui/page_scenario_live.py"),
    ("ui/page_storyboard.py",     "ui/page_storyboard_live.py"),
    ("ui/dialog_shot.py",         "ui/dialog_shot_live.py"),
    ("ui/page_castings.py",       "ui/page_castings_live.py"),
    ("ui/page_accessories.py",    "ui/page_accessories_live.py"),
    ("ui/page_vehicles.py",       "ui/page_vehicles_live.py"),
    ("ui/page_projects.py",       "ui/page_projects_live.py"),
    ("ui/tab_history.py",         "ui/tab_history_live.py"),
    ("ui/assistant_panel.py",     "ui/assistant_panel_live.py"),
    ("ui/dialog_user_manual.py",  "ui/dialog_user_manual_live.py"),
    ("ui/dialog_contact.py",      "ui/dialog_contact_live.py"),
]

# Divergences VOULUES (fonctionnalités spécifiques à un côté) — non signalées.
# À enrichir au fil des sessions pour garder le rapport lisible.
EXPECTED_ONLY_LIVE = {
    "ui/tab_t2v_live.py": {
        "_make_seq_btn", "_apply_seq_style", "_set_seq_mode",
        "_refresh_bref", "_on_pick_bref", "_on_clear_bref",
        "_get_mapping_keyframes",
    },
    "ui/page_scenario_live.py": {
        # Musique du set, façade, mode Live/Mapping, fenêtres dédiées…
        "_refresh_music_display", "_make_music_chip", "_remove_music",
        "_edit_bpm", "_on_add_music", "_on_analyze_music",
        "_open_music_analysis_window", "_text_with_music",
        "_refresh_building_display", "_on_pick_building", "_on_clear_building",
        "_on_isolate_building", "_on_isolate_done", "_on_isolate_failed",
        "_make_mode_btn", "_set_live_mode", "_apply_mode_style",
        "_apply_layout", "_apply_decoupage", "_open_decoupage_window",
        # Extraction calibrée Live (remplace les extracteurs Cinéma)
        "_live_extract_dialog",
        # Refs visuelles 2026-06-11 : persistance + bibliothèque + chat DA
        # (chantier à reporter vers Cinéma après validation Live)
        "_start_refs_analysis", "_on_load_saved_analysis", "_apply_saved_analysis",
        # Assistant de calage mapping (2026-06-11) — Live uniquement
        "_on_generate_calage",
    },
    "ui/page_storyboard_live.py": {
        "_visible_order", "_load_conductor_tracks", "_on_music_align",
        # P2 « fusion » : côté Cinéma la fenêtre « Garder/Séparer » vit dans le
        # dialogue dédié (StoryboardGenerateDialog) ; côté Live la génération est
        # inline dans la page → l'ask est une méthode de page (Live uniquement).
        "_ask_merge_decision",
    },
}
EXPECTED_ONLY_CINEMA = {
    "ui/tab_t2v_live.py": {
        # DaVinci purgé côté Live (voulu)
        "_DaVinciBar", "_check_davinci_connection",
        "_on_davinci_connection_changed", "_refresh", "_on_connect",
        # Sélection par GROUPE couleur (plans récurrents) dans le StoryboardSelector
        # — feature Cinéma (Rendu/Audio) ; reportable au Live si besoin.
        "_rebuild_group_chips", "_select_color_group",
        # Synchronisation labiale (lip-sync) en post-traitement dans RENDU & AUDIO —
        # toggle + sélecteur de moteur (Sync 2 Pro défaut) + file ; feature Cinéma
        # (le Live a son propre lip-sync par keyframes/mapping). Reportable si besoin.
        "_advance_after_clip", "_start_shot_lipsync",
        "_on_shot_lipsync_done", "_on_shot_lipsync_failed",
        # Enchaînement des moods (RENDU & AUDIO) : résout le mood actif d'un plan
        # pour l'image de fin (mood i+1). Le Live a son propre mécanisme de
        # keyframes mapping (_get_mapping_keyframes) → Cinéma-only.
        "_mood_path_for_shot",
    },
    "ui/page_scenario_live.py": {
        # Pas de Décors ni de HMC dans le Live (handlers supprimés, validé)
        "_on_gen_decors", "_on_gen_hmc",
        # Onglet « Mise en page PANDORA » Cinéma : helpers de persistance/reset
        # (le Live gère sa mise en page inline dans _open_scenario) — voulu.
        "_clear_layout", "_restore_layout",
        # Sauvegarder/Ouvrir le scénario en fichier (dossier Scénario) — Cinéma only.
        "_on_save_scenario_file", "_on_open_scenario_file",
        # Musique du film : popup AVANT analyse pour choisir film (moments clés) /
        # clip (début→fin). Notion propre au Cinéma — le Live cale en continu (set).
        "_choose_music_mode",
        # Rechargement de l'éditeur vide depuis le disque (affiche le scénario
        # reconstruit par la synchro Storyboard) — Cinéma ; reportable au Live.
        "_reload_if_empty_editor",
    },
    "ui/page_storyboard_live.py": {
        # PORTÉS au Live le 2026-07-01 (« tout lancer ») → désormais des DEUX côtés :
        # Sauvegarder/Ouvrir storyboard + Pitch deck ; clic droit Dupliquer +
        # Libellé couleur (contextMenuEvent, _on_duplicate, _set_label).
        # RESTENT Cinéma-only (validé : « plans récurrents » sans objet en live) :
        # FLAG récurrent + analyse IA récurrence + helper de contraste texte.
        "_set_recurrent",
        "_on_detect_recurrent", "_on_recurrent_done", "_on_recurrent_fail",
        "_contrast_text",
    },
    "ui/dialog_contact_live.py": {
        # Divergence LÉGÈRE voulue (2026-06-12) : le Live est une sous-classe
        # qui ne surcharge que _WA_GROUP/_WA_LINK (groupe WhatsApp Live) —
        # tout le corps du dialogue reste hérité de Cinéma, d'où ces méthodes
        # « uniquement Cinéma » aux yeux du radar.
        "__init__", "_copy_email", "_open_eula", "_open_whatsapp",
    },
}


def _defs(path: str) -> dict:
    """{nom_qualifié: source_normalisée} des fonctions/méthodes du fichier.
    On ne descend PAS dans le corps des fonctions (les helpers imbriqués font
    partie de la source de leur parent — comparer le parent suffit)."""
    with open(path, encoding="utf-8-sig") as f:   # -sig : tolère le BOM
        src = f.read()
    tree = ast.parse(src)
    out = {}

    def walk(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                seg = ast.get_source_segment(src, child) or ""
                out[f"{prefix}{child.name}"] = " ".join(seg.split())
                # pas de descente : les fonctions imbriquées restent dans le parent
            elif isinstance(child, ast.ClassDef):
                out.setdefault(f"{prefix}{child.name}", "")
                walk(child, f"{prefix}{child.name}.")
            else:
                walk(child, prefix)

    walk(tree)
    return out


def _short(name: str) -> str:
    return name.split(".")[-1]


def report(verbose: bool = False) -> int:
    print("Radar de divergence PANDORA Cinéma ↔ Live")
    print("=" * 72)
    total_alerts = 0
    for cin_rel, live_rel in PAIRS:
        cin, live = os.path.join(ROOT, cin_rel), os.path.join(ROOT, live_rel)
        if not (os.path.isfile(cin) and os.path.isfile(live)):
            print(f"\n⚠ paire incomplète : {cin_rel} / {live_rel}")
            continue
        with open(cin, encoding="utf-8-sig") as f:
            cl = f.readlines()
        with open(live, encoding="utf-8-sig") as f:
            ll = f.readlines()
        if "ALIAS SANS DOUBLON" in "".join(ll[:6]):
            print(f"\n{cin_rel}  ↔  {live_rel}")
            print("  ✓ alias — zéro doublon (réexporte la classe Cinéma ; "
                  "procédure de divergence dans l'en-tête)")
            continue
        if "Divergence ASSUMÉE" in "".join(ll[:8]):
            # Contenu distinct PAR NATURE (ex. manuel Live) : sous-classe du
            # squelette Cinéma, sections propres — pas de comparaison méthode
            # à méthode, l'en-tête documente la divergence.
            print(f"\n{cin_rel}  ↔  {live_rel}")
            print("  ✓ divergence totale documentée (sous-classe, contenu Live dédié)")
            continue
        ratio = difflib.SequenceMatcher(None, cl, ll).ratio() * 100

        dc, dl = _defs(cin), _defs(live)
        only_live   = sorted(set(dl) - set(dc))
        only_cinema = sorted(set(dc) - set(dl))
        modified    = sorted(n for n in (set(dc) & set(dl))
                             if dc[n] and dl[n] and dc[n] != dl[n])

        exp_l = EXPECTED_ONLY_LIVE.get(live_rel, set())
        exp_c = EXPECTED_ONLY_CINEMA.get(live_rel, set())

        def _expected(name: str, expected: set) -> bool:
            # attendu si N'IMPORTE QUEL segment du nom qualifié est listé
            # (couvre « _DaVinciBar » pour « _DaVinciBar.__init__ »)
            return any(part in expected for part in name.split("."))

        only_live_alert   = [n for n in only_live if not _expected(n, exp_l)]
        only_cinema_alert = [n for n in only_cinema if not _expected(n, exp_c)]

        print(f"\n{cin_rel}  ↔  {live_rel}")
        print(f"  similarité {ratio:.0f}% · {len(modified)} méthode(s) divergente(s) "
              f"· +{len(only_live)} Live · +{len(only_cinema)} Cinéma")
        if only_live_alert:
            total_alerts += len(only_live_alert)
            print(f"  → uniquement LIVE (à évaluer pour Cinéma ?) : "
                  + ", ".join(_short(n) for n in only_live_alert[:10])
                  + (" …" if len(only_live_alert) > 10 else ""))
        if only_cinema_alert:
            total_alerts += len(only_cinema_alert)
            print(f"  → uniquement CINÉMA (à évaluer pour Live ?) : "
                  + ", ".join(_short(n) for n in only_cinema_alert[:10])
                  + (" …" if len(only_cinema_alert) > 10 else ""))
        if verbose and modified:
            print("  → divergentes : " + ", ".join(_short(n) for n in modified[:15])
                  + (" …" if len(modified) > 15 else ""))

    print("\n" + "=" * 72)
    print(f"{total_alerts} élément(s) hors divergences attendues — "
          "à évaluer pour report manuel.")
    print("Rappel : on ne synchronise JAMAIS automatiquement ; on reporte à la main, "
          "puis on lance tools/test_cinema.py ET tools/test_live.py.")
    return 0


if __name__ == "__main__":
    sys.exit(report(verbose="-v" in sys.argv))
