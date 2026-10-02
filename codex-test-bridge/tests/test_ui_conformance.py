import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = ROOT.parent / "codex-ui-test-fixtures"
SCENARIOS = FIXTURES_ROOT / "scenarios" / "ui-conformance"
sys.path.insert(0, str(ROOT))

from ui_conformance import build_conformance_report, load_conformance_scenarios, validate_conformance_coverage
from ui_worker import UiWorkerError


class UiConformanceTests(unittest.TestCase):
    def test_repository_conformance_scenarios_cover_every_fixture_action(self):
        scenarios = load_conformance_scenarios([SCENARIOS])
        sources = validate_conformance_coverage(scenarios)
        self.assertIn("field.text", sources)
        self.assertIn("field.text-document-programmatic", sources)
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

    def test_text_document_fixture_checks_programmatic_reassignment(self):
        scenarios = load_conformance_scenarios([SCENARIOS])
        scenario = next(
            item for item in scenarios
            if "field.text-document-programmatic" in item["cases"]
        )
        steps = scenario["data"]["steps"]
        reset_index = next(
            index for index, step in enumerate(steps)
            if step.get("action") == "invokeFormCommand" and step.get("command") == "Reset"
        )
        self.assertEqual(
            steps[reset_index + 1],
            {
                "action": "assertField",
                "form": "fixture",
                "field": {"objectName": "TextDocumentValue"},
                "expected": "fixture text document",
            },
        )
        self.assertTrue(any(
            step.get("action") == "inputText"
            and step.get("field", {}).get("objectName") == "TextDocumentValue"
            and step.get("value") == "changed text document"
            for step in steps[:reset_index]
        ))

    def test_generic_task_form_fixture_is_created_before_open(self):
        scenarios = load_conformance_scenarios([SCENARIOS])
        scenario = next(item for item in scenarios if "form.lifecycle" in item["cases"])
        steps = scenario["data"]["steps"]
        task_open_index = next(
            index for index, step in enumerate(steps)
            if step.get("action") == "openForm" and step.get("metadataKind") == "task"
        )
        task_uuid = steps[task_open_index]["uuid"]
        self.assertTrue(any(
            step.get("action") == "openTaskExecutionForm"
            and step.get("metadataName") == "CodexUIFixtureTask"
            and step.get("uuid") == task_uuid
            and step.get("formName") == "Задача.CodexUIFixtureTask.Форма.ФормаВыполнения"
            for step in steps[:task_open_index]
        ))

    def test_missing_fixture_case_is_rejected(self):
        scenarios = load_conformance_scenarios([SCENARIOS])
        scenarios[0] = dict(scenarios[0], cases=[])
        with self.assertRaisesRegex(UiWorkerError, "Fixture conformance cases are missing"):
            validate_conformance_coverage(scenarios)

    def test_declared_case_without_assigned_action_is_rejected(self):
        scenarios = load_conformance_scenarios([SCENARIOS])
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
        scenarios = load_conformance_scenarios([SCENARIOS])
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
        scenarios = load_conformance_scenarios([SCENARIOS])
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
                source = (FIXTURES_ROOT / "src" / relative).read_text(encoding="utf-8-sig")
                self.assertIn(generated_type, source)
        form = (FIXTURES_ROOT / "src/CommonForms/CodexUIConformance/Ext/Form.xml").read_text(encoding="utf-8-sig")
        self.assertIn("cfg:CatalogRef.CodexUIFixtureCatalog", form)
        self.assertIn("cfg:ChartOfCharacteristicTypesRef.CodexUIFixtureCharacteristics", form)
        self.assertIn('name="CompositeValue"', form)
        self.assertIn('name="ReferenceRows"', form)

    def test_fixture_metadata_is_not_part_of_bridge_extension(self):
        bridge_configuration = (ROOT / "src" / "Configuration.xml").read_text(encoding="utf-8-sig")
        fixture_configuration = (FIXTURES_ROOT / "src" / "Configuration.xml").read_text(encoding="utf-8-sig")
        fixture_names = {
            "CodexUIFixture", "CodexUIFixtureCommand", "CodexUIConformance",
            "CodexUIFixtureCatalog", "CodexUIFixtureDocument", "CodexUIFixtureStatus",
            "CodexUIFixtureProcessor", "CodexUIFixtureCharacteristics",
            "CodexUIFixtureAccounts", "CodexUIFixtureCalculationTypes",
            "CodexUIFixtureProcess", "CodexUIFixtureTask",
        }
        for name in fixture_names:
            with self.subTest(name=name):
                self.assertNotIn(f">{name}<", bridge_configuration)
                self.assertIn(f">{name}<", fixture_configuration)
        bridge_text = "\n".join(
            path.read_text(encoding="utf-8-sig")
            for path in (ROOT / "src").rglob("*")
            if path.is_file()
        )
        self.assertNotIn("CodexUIFixture", bridge_text)
        self.assertNotIn("CodexUIConformance", bridge_text)
        self.assertFalse((ROOT / "src" / "Catalogs").exists())
        self.assertFalse((ROOT / "src" / "CommonForms").exists())

    def test_bridge_runtime_is_not_part_of_fixture_extension(self):
        fixture_configuration = (FIXTURES_ROOT / "src" / "Configuration.xml").read_text(encoding="utf-8-sig")
        for name in ("CodexUIJobsServer", "CodexTestBridge", "CodexNavigate", "CodexUIJobs"):
            with self.subTest(name=name):
                self.assertNotIn(f">{name}<", fixture_configuration)
        for directory in ("CommonModules", "HTTPServices", "InformationRegisters"):
            with self.subTest(directory=directory):
                self.assertFalse((FIXTURES_ROOT / "src" / directory).exists())


if __name__ == "__main__":
    unittest.main()
