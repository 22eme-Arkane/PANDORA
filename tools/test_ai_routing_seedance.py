"""Tests purs du chantier assistants IA + bible Seedance.

Ce fichier ne lance ni l'application ni un serveur, ne contacte aucun fournisseur et
ne lit/écrit jamais la vraie configuration utilisateur.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

# L'exécution directe ``python tools/test_….py`` place ``tools/`` en tête ; rendre
# la racine du dépôt importable sans dépendre d'une variable d'environnement.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


CATALOGS = {
    "characters": [{
        "id": "char-jesus", "name": "Jésus",
        "description": "homme émacié, visage anguleux",
        "costume": "robe blanche déchirée", "hmc_ids": ["hmc-robe"],
    }],
    "decors": [{
        "id": "decor-canyon", "name": "Canyon ocre",
        "description": "parois stratifiées, arbre mort au centre",
    }],
    "accessories": [{
        "id": "prop-couronne", "name": "Couronne d'épines",
        "materials": "branches sèches torsadées",
    }],
    "hmc": [{
        "id": "hmc-robe", "name": "Robe blanche déchirée",
        "description": "lin blanc cassé, ourlets effilochés",
    }],
    "vehicles": [{
        "id": "veh-jeep", "name": "Jeep sable",
        "description": "carrosserie beige mate, bâche kaki",
    }],
}


class _FakeItem:
    def setEnabled(self, _enabled):
        pass


class _FakeCombo:
    """Minimum de QComboBox requis par les helpers, sans démarrer Qt."""

    def __init__(self):
        self.rows = []
        self.index = 0

    def blockSignals(self, _blocked):
        pass

    def clear(self):
        self.rows.clear()
        self.index = 0

    def addItem(self, label, data=None):
        self.rows.append((label, data))

    def count(self):
        return len(self.rows)

    def model(self):
        return self

    def item(self, _index):
        return _FakeItem()

    def itemData(self, index):
        return self.rows[index][1]

    def setCurrentIndex(self, index):
        self.index = index

    def currentData(self):
        return self.rows[self.index][1]


class RoutingTests(unittest.TestCase):
    def test_profiles_ne_sortent_jamais_de_leur_famille(self):
        from core.ai_registry import TASKS, resolve_engine

        for task, _label in TASKS:
            anthropic = resolve_engine({"ai_profile": "anthropic_optimized"}, task)
            openai = resolve_engine({"ai_profile": "openai_optimized"}, task)
            self.assertEqual(anthropic["provider"], "anthropic", task)
            self.assertEqual(openai["provider"], "openai", task)

        # Les anciens overrides incompatibles ne doivent jamais percer la
        # frontière stricte d'un profil optimisé.
        openai_cfg = {
            "ai_profile": "openai_optimized",
            "ai_task_engines": {task: "claude" for task, _label in TASKS},
        }
        anthropic_cfg = {
            "ai_profile": "anthropic_optimized",
            "ai_task_engines": {task: "openai_sol" for task, _label in TASKS},
        }
        for task, _label in TASKS:
            self.assertEqual(resolve_engine(openai_cfg, task)["provider"], "openai", task)
            self.assertEqual(resolve_engine(anthropic_cfg, task)["provider"], "anthropic", task)

    def test_routage_openai_attendu(self):
        from core.ai_registry import resolve_engine

        cfg = {"ai_profile": "openai_optimized"}
        self.assertEqual(resolve_engine(cfg, "storyboard_gen")["model"], "gpt-5.6-sol")
        self.assertEqual(resolve_engine(cfg, "vision")["model"], "gpt-5.6-terra")
        self.assertEqual(resolve_engine(cfg, "translate")["model"], "gpt-5.6-luna")

    def test_modele_decouvert_et_multimodal(self):
        from core.ai_registry import engine
        from core.ai_provider import _openai_messages

        self.assertEqual(engine("openai:gpt-test")["model"], "gpt-test")
        messages = _openai_messages("S", [{"role": "user", "content": [
            {"type": "image", "source": {
                "type": "base64", "media_type": "image/png", "data": "AAAA"}},
            {"type": "text", "text": "décris"},
        ]}])
        content = messages[-1]["content"]
        self.assertTrue(content[0]["image_url"]["url"].startswith("data:image/png;base64,"))
        self.assertEqual(content[1]["text"], "décris")

    def test_menu_taches_suit_immediatement_le_profil_openai(self):
        from core.ai_registry import engine
        from ui.ai_model_selector import populate_task_engines

        combo = _FakeCombo()
        cfg = {
            "ai_profile": "openai_optimized",
            "ai_task_engines": {"screenplay": "claude"},
        }
        populate_task_engines(combo, cfg, "screenplay", "claude")
        self.assertEqual(combo.currentData(), "")
        self.assertIn("GPT-5.6 Sol", combo.rows[0][0])
        for _label, key in combo.rows[1:]:
            if key:
                self.assertEqual(engine(key, cfg)["group"], "openai")


class VisualContextTests(unittest.TestCase):
    def test_reliaison_et_bible_complete(self):
        from core.visual_context import build_visual_context, enrich_shot_entities

        shot = {
            "number": 2,
            "scene_title": "Jésus traverse le Canyon ocre près de la Jeep sable",
            "seedance_prompt": "Il ajuste la Couronne d'épines.",
            "character_ids": [], "accessory_ids": [], "vehicle_ids": [],
            "hmc_ids": [],
        }
        enrich_shot_entities(shot, CATALOGS)
        self.assertEqual(shot["character_ids"], ["char-jesus"])
        self.assertEqual(shot["decor_id"], "decor-canyon")
        self.assertEqual(shot["accessory_ids"], ["prop-couronne"])
        self.assertEqual(shot["vehicle_ids"], ["veh-jeep"])
        self.assertEqual(shot["hmc_ids"], ["hmc-robe"])

        bible = build_visual_context(shot, CATALOGS)
        self.assertEqual(bible["characters"][0]["costume"], "robe blanche déchirée")
        self.assertIn("arbre mort", bible["decor"]["description"])
        self.assertEqual(bible["vehicles"][0]["name"], "Jeep sable")

    def test_mise_en_page_declenche_le_composeur(self):
        from api.video_prompt import should_compose
        from core.decoupage_layout import layout_segments_to_cinema_shots

        layout = """SÉQUENCE 1 — Désert
P01 | Gros plan | Travelling avant | Axe frontal | ~7s
Jésus traverse le Canyon ocre avec la Jeep sable.
→ SEEDANCE: Jésus ajuste la Couronne d'épines et marche vers la Jeep sable.
"""
        with patch("core.visual_context.load_catalogs", return_value=CATALOGS):
            shots = layout_segments_to_cinema_shots(layout)
        self.assertEqual(len(shots), 1)
        self.assertEqual(shots[0]["character_ids"], ["char-jesus"])
        self.assertEqual(shots[0]["decor_id"], "decor-canyon")
        self.assertTrue(should_compose(shots[0]["seedance_prompt"]))


class PromptValidationTests(unittest.TestCase):
    def test_quota_openai_n_est_pas_annonce_comme_saturation(self):
        from core.ai_provider import humanize_ai_error

        raw = ("Error code: 429 - {'error': {'message': 'You exceeded your current "
               "quota, please check your plan and billing details.', "
               "'type': 'insufficient_quota'}}")
        message = humanize_ai_error(raw)
        self.assertIn("Crédits OpenAI épuisés", message)
        self.assertNotIn("saturé", message)

    def test_validation_bloque_preambule_et_dialogue_modifie(self):
        from api.video_prompt import validate_composed_prompt

        source = 'Elle dit "Reste ici" puis ferme la porte.'
        bad = validate_composed_prompt("Voici le prompt : elle part.", source)
        self.assertFalse(bad["valid"])
        self.assertTrue(any("dialogue" in error for error in bad["errors"]))

    def test_bible_est_injectee_dans_le_message(self):
        from api.video_prompt import _build_user_message

        msg = _build_user_message("[ACTION]\nMarche", "style", "sunset", 7,
                                  "personnage", True, "vent", '{"decor":"canyon"}')
        self.assertIn("BIBLE VISUELLE CANONIQUE", msg)
        self.assertIn('"decor":"canyon"', msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
