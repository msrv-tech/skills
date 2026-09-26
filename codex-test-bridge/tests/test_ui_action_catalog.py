import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ui_action_catalog import action_names, load_ui_action_catalog, public_action_names
from ui_worker import NATIVE_UI_ACTIONS


class UiActionCatalogTests(unittest.TestCase):
    def test_catalog_is_the_worker_and_schema_source_of_truth(self):
        catalog = load_ui_action_catalog()
        self.assertEqual(NATIVE_UI_ACTIONS, action_names())
        schema = json.loads((ROOT / "ui-scenario.schema.json").read_text(encoding="utf-8"))
        schema_actions = set(schema["$defs"]["step"]["properties"]["action"]["enum"])
        self.assertEqual(schema_actions, action_names(include_internal=False, include_aliases=True))
        self.assertEqual(
            set(schema["$defs"]["step"]["properties"]["elementType"]["enum"]),
            set(catalog["elementTypes"]),
        )

    def test_bsl_dispatcher_and_capabilities_match_catalog(self):
        dispatcher = (ROOT / "src" / "Ext" / "ManagedApplicationModule.bsl").read_text(encoding="utf-8-sig")
        dispatched = {match.group(1).casefold() for match in re.finditer(r'Действие\s*=\s*"([A-Za-z]+)"', dispatcher)}
        self.assertEqual(dispatched, {name.casefold() for name in action_names()})

        http_module = (
            ROOT / "src" / "HTTPServices" / "CodexTestBridge" / "Ext" / "Module.bsl"
        ).read_text(encoding="utf-8-sig")
        match = re.search(r'ИмяДействия Из СтрРазделить\("([^"]+)"', http_module)
        self.assertIsNotNone(match)
        capabilities = set(match.group(1).split(","))
        self.assertEqual(capabilities, public_action_names())

    def test_every_action_has_an_explicit_coverage_class_and_case(self):
        catalog = load_ui_action_catalog()
        for action in catalog["actions"]:
            with self.subTest(action=action["name"]):
                self.assertTrue(action["cases"])
                self.assertTrue(action["backends"])
                self.assertIn(action["coverage"], {"fixture", "integration", "platform", "internal", "alias"})
                for variant in action.get("variants", []):
                    self.assertTrue(variant["id"])
                    self.assertTrue(variant["match"])

    def test_every_public_action_has_executable_fixture_coverage(self):
        public = [
            action for action in load_ui_action_catalog()["actions"]
            if action["visibility"] == "public"
        ]
        self.assertEqual(len(public), 49)
        self.assertTrue(all(action["coverage"] == "fixture" for action in public))


if __name__ == "__main__":
    unittest.main()
