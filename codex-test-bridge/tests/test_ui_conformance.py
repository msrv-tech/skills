import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ui_conformance import build_conformance_report, load_conformance_scenarios, validate_conformance_coverage
from ui_worker import UiWorkerError


class UiConformanceTests(unittest.TestCase):
    def test_repository_conformance_scenarios_cover_every_fixture_action(self):
        scenarios = load_conformance_scenarios([ROOT / "examples" / "ui-conformance"])
        sources = validate_conformance_coverage(scenarios)
        self.assertIn("field.text", sources)
        self.assertIn("button.form-command", sources)
        self.assertIn("table.edit-cell", sources)
        self.assertIn("reference.characteristic", sources)
        self.assertIn("reference.choice-form-selection", sources)
        report = build_conformance_report(scenarios)
        self.assertTrue(report["ok"])
        self.assertEqual(report["summary"]["publicActions"], 49)
        self.assertEqual(report["summary"]["fixtureActions"], 49)
        self.assertEqual(report["summary"]["failed"], 0)
        self.assertGreater(report["summary"]["variants"], 0)

    def test_missing_fixture_case_is_rejected(self):
        scenarios = load_conformance_scenarios([ROOT / "examples" / "ui-conformance"])
        scenarios[0] = dict(scenarios[0], cases=[])
        with self.assertRaisesRegex(UiWorkerError, "Fixture conformance cases are missing"):
            validate_conformance_coverage(scenarios)

    def test_declared_case_without_assigned_action_is_rejected(self):
        scenarios = load_conformance_scenarios([ROOT / "examples" / "ui-conformance"])
        changed = []
        for scenario in scenarios:
            copy = dict(scenario)
            copy["data"] = dict(scenario["data"])
            copy["data"]["steps"] = [
                step for step in scenario["data"]["steps"]
                if step.get("action") != "setCheckbox"
            ]
            changed.append(copy)
        with self.assertRaisesRegex(UiWorkerError, "Fixture action setCheckbox is not invoked"):
            validate_conformance_coverage(changed)

    def test_missing_declared_action_variant_is_rejected(self):
        scenarios = load_conformance_scenarios([ROOT / "examples" / "ui-conformance"])
        changed = []
        for scenario in scenarios:
            copy = dict(scenario)
            copy["data"] = dict(scenario["data"])
            copy["data"]["steps"] = [
                step for step in scenario["data"]["steps"]
                if not (step.get("action") == "setCheckbox" and step.get("checked") is False)
            ]
            changed.append(copy)
        with self.assertRaisesRegex(UiWorkerError, "variant unchecked"):
            validate_conformance_coverage(changed)

    def test_runtime_results_are_projected_to_each_action(self):
        scenarios = load_conformance_scenarios([ROOT / "examples" / "ui-conformance"])
        suite_result = {
            "scenarios": [
                {"source": str(scenario["path"]), "ok": True}
                for scenario in scenarios
            ]
        }
        report = build_conformance_report(scenarios, suite_result)
        self.assertTrue(report["ok"])
        fixture = [action for action in report["actions"] if action["coverage"] == "fixture"]
        self.assertTrue(fixture)
        self.assertTrue(all(action["status"] == "passed" for action in fixture))

    def test_reference_fixture_contains_typical_metadata_objects(self):
        expected = {
            "Catalogs/CodexUIFixtureCatalog.xml": "CatalogRef.CodexUIFixtureCatalog",
            "Documents/CodexUIFixtureDocument.xml": "DocumentRef.CodexUIFixtureDocument",
            "ChartsOfCharacteristicTypes/CodexUIFixtureCharacteristics.xml": "ChartOfCharacteristicTypesRef.CodexUIFixtureCharacteristics",
            "ChartsOfAccounts/CodexUIFixtureAccounts.xml": "ChartOfAccountsRef.CodexUIFixtureAccounts",
            "ChartsOfCalculationTypes/CodexUIFixtureCalculationTypes.xml": "ChartOfCalculationTypesRef.CodexUIFixtureCalculationTypes",
            "Enums/CodexUIFixtureStatus.xml": "EnumRef.CodexUIFixtureStatus",
        }
        for relative, generated_type in expected.items():
            with self.subTest(relative=relative):
                source = (ROOT / "src" / relative).read_text(encoding="utf-8-sig")
                self.assertIn(generated_type, source)
        form = (ROOT / "src/CommonForms/CodexUIConformance/Ext/Form.xml").read_text(encoding="utf-8-sig")
        self.assertIn("cfg:CatalogRef.CodexUIFixtureCatalog", form)
        self.assertIn("cfg:ChartOfCharacteristicTypesRef.CodexUIFixtureCharacteristics", form)
        self.assertIn('name="CompositeValue"', form)
        self.assertIn('name="ReferenceRows"', form)


if __name__ == "__main__":
    unittest.main()
