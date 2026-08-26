import unittest
import sys
import json
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scenario_runner import (
    ScenarioError,
    ScenarioRunner,
    check_assertion,
    collect_scenario_files,
    read_path,
    redact_paths,
    run_suite,
    save_junit_report,
    substitute,
    validate_scenario,
)


class ScenarioRunnerTests(unittest.TestCase):
    def test_paths_and_substitution(self):
        context = {"created": {"ref": {"uuid": "abc"}}}
        self.assertEqual(read_path(context, "created.ref.uuid"), "abc")
        self.assertEqual(substitute("${created.ref.uuid}", context), "abc")
        self.assertEqual(substitute("id=${created.ref.uuid}", context), "id=abc")

    def test_assertions(self):
        self.assertTrue(check_assertion([1, 2], "contains", 2))
        self.assertTrue(check_assertion("Контрагент", "matches", "Контр"))
        self.assertTrue(check_assertion([], "empty"))

    def test_scenario_tracks_and_cleans_created_object(self):
        calls = []

        def send(payload):
            calls.append(payload)
            if payload["command"] == "WriteObject":
                return {"ok": True, "ref": {"uuid": "new-uuid"}}
            if payload["command"] == "GetObject":
                return {"ok": True, "ref": {"uuid": payload["uuid"]}}
            return {"ok": True}

        report = ScenarioRunner(send).run({
            "name": "smoke",
            "steps": [
                {
                    "saveAs": "item",
                    "request": {"command": "WriteObject", "kind": "catalog", "name": "Контрагенты", "fields": {}},
                },
                {
                    "request": {"command": "GetObject", "kind": "catalog", "name": "Контрагенты", "uuid": "${item.ref.uuid}"},
                    "assert": [{"path": "ref.uuid", "expected": "new-uuid"}],
                },
            ],
        })

        self.assertEqual(report["status"], "passed")
        self.assertEqual(calls[-1]["command"], "DeleteObject")
        self.assertEqual(calls[-1]["uuid"], "new-uuid")

    def test_retry_until_assertion_passes(self):
        attempts = iter([0, 1, 2])

        def send(_payload):
            return {"ok": True, "count": next(attempts)}

        report = ScenarioRunner(send, sleep=lambda _: None).run({
            "cleanup": False,
            "steps": [{
                "request": {"command": "Query", "text": "test"},
                "retry": {"attempts": 3, "delaySeconds": 0},
                "assert": [{"path": "count", "operator": "gte", "expected": 2}],
            }],
        })
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["steps"][0]["attempts"], 3)

    def test_failed_step_is_reported_and_cleanup_still_runs(self):
        calls = []

        def send(payload):
            calls.append(payload)
            if payload["command"] == "WriteObject":
                return {"ok": True, "ref": {"uuid": "failed-run-object"}}
            if payload["command"] == "Query":
                return {"ok": True, "count": 0}
            return {"ok": True}

        report = ScenarioRunner(send).run({
            "steps": [
                {"request": {"command": "WriteObject", "kind": "catalog", "name": "Контрагенты"}},
                {
                    "name": "failing assertion",
                    "request": {"command": "Query", "text": "test"},
                    "assert": [{"path": "count", "operator": "gte", "expected": 1}],
                },
            ],
        })

        self.assertFalse(report["ok"])
        self.assertEqual(report["steps"][-1]["status"], "failed")
        self.assertEqual(calls[-1]["command"], "DeleteObject")

    def test_created_object_is_cleaned_when_creation_step_assertion_fails(self):
        calls = []

        def send(payload):
            calls.append(payload)
            if payload["command"] == "WriteObject":
                return {"ok": True, "ref": {"uuid": "orphan-candidate"}}
            return {"ok": True}

        report = ScenarioRunner(send).run({
            "steps": [{
                "request": {"command": "WriteObject", "kind": "catalog", "name": "Контрагенты"},
                "assert": [{"path": "ref.uuid", "operator": "eq", "expected": "wrong"}],
            }],
        })

        self.assertFalse(report["ok"])
        self.assertEqual(calls[-1]["command"], "DeleteObject")
        self.assertEqual(calls[-1]["uuid"], "orphan-candidate")

    def test_transport_error_is_retried_and_reported(self):
        call_count = 0

        def send(_payload):
            nonlocal call_count
            call_count += 1
            raise TimeoutError("bridge did not respond")

        report = ScenarioRunner(send, sleep=lambda _: None).run({
            "cleanup": False,
            "steps": [{
                "request": {"command": "Health"},
                "retry": {"attempts": 2, "delaySeconds": 0},
            }],
        })

        self.assertEqual(call_count, 2)
        self.assertEqual(report["steps"][0]["attempts"], 2)
        self.assertIn("Transport error", report["steps"][0]["error"])

    def test_explicit_finally_runs_in_reverse_order(self):
        calls = []

        def send(payload):
            calls.append(payload["command"])
            return {"ok": True}

        report = ScenarioRunner(send).run({
            "cleanup": False,
            "steps": [{"request": {"command": "Health"}}],
            "finally": [
                {"command": "FirstCleanup"},
                {"command": "SecondCleanup"},
            ],
        })

        self.assertTrue(report["ok"])
        self.assertEqual(calls, ["Health", "SecondCleanup", "FirstCleanup"])

    def test_cleanup_failure_changes_successful_run_status(self):
        def send(payload):
            if payload["command"] == "BrokenCleanup":
                return {"ok": False, "error": "cannot cleanup"}
            return {"ok": True}

        report = ScenarioRunner(send).run({
            "cleanup": False,
            "steps": [{"request": {"command": "Health"}}],
            "finally": [{"command": "BrokenCleanup"}],
        })

        self.assertFalse(report["ok"])
        self.assertEqual(report["status"], "cleanupFailed")

    def test_validation_rejects_invalid_scenarios(self):
        with self.assertRaises(ScenarioError):
            validate_scenario({"steps": []})
        with self.assertRaises(ScenarioError):
            validate_scenario({"steps": [{"request": {"command": "Health"}, "saveAs": "run"}]})
        with self.assertRaises(ScenarioError):
            validate_scenario({"steps": [{"request": {"command": "Health"}, "retry": {"attempts": 0}}]})
        with self.assertRaises(ScenarioError):
            validate_scenario({"steps": [{"request": {"command": "Health"}, "assert": [{"path": "ok", "operator": "unknown"}]}]})

    def test_request_fields_can_be_redacted_in_report(self):
        request = {"command": "WriteObject", "fields": {"Password": "secret", "Name": "safe"}}
        self.assertEqual(redact_paths(request, ["fields.Password"])["fields"]["Password"], "***")
        self.assertEqual(request["fields"]["Password"], "secret")

    def test_redaction_does_not_change_request_or_cleanup_tracking(self):
        calls = []

        def send(payload):
            calls.append(payload)
            if payload["command"] == "WriteObject":
                return {"ok": True, "ref": {"uuid": "redacted-object"}}
            return {"ok": True}

        report = ScenarioRunner(send).run({
            "steps": [{
                "request": {
                    "command": "WriteObject",
                    "kind": "catalog",
                    "name": "Контрагенты",
                    "fields": {"Password": "secret"},
                },
                "redactRequest": ["fields.Password"],
            }],
        })

        self.assertEqual(calls[0]["fields"]["Password"], "secret")
        self.assertEqual(report["steps"][0]["request"]["fields"]["Password"], "***")
        self.assertEqual(calls[-1]["uuid"], "redacted-object")

    def test_suite_collects_scenarios_and_writes_junit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            valid = root / "valid.scenario.json"
            invalid = root / "invalid.scenario.json"
            schema = root / "ignored.schema.json"
            valid.write_text(json.dumps({"name": "valid", "cleanup": False, "steps": [{"request": {"command": "Health"}}]}), encoding="utf-8")
            invalid.write_text(json.dumps({"steps": []}), encoding="utf-8")
            schema.write_text("{}", encoding="utf-8")

            files = collect_scenario_files(root)
            suite = run_suite(ScenarioRunner(lambda _payload: {"ok": True}), files)
            junit = root / "report.xml"
            save_junit_report(suite, junit)

            self.assertEqual([path.name for path in files], ["invalid.scenario.json", "valid.scenario.json"])
            self.assertEqual(suite["total"], 2)
            self.assertEqual(suite["passed"], 1)
            self.assertEqual(suite["failed"], 1)
            xml_root = ET.parse(junit).getroot()
            self.assertEqual(xml_root.attrib["tests"], "2")
            self.assertEqual(xml_root.attrib["failures"], "1")

    def test_suite_fail_fast_stops_after_invalid_scenario(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "01-invalid.scenario.json"
            second = root / "02-valid.scenario.json"
            first.write_text('{"steps": []}', encoding="utf-8")
            second.write_text('{"steps": [{"request": {"command": "Health"}}]}', encoding="utf-8")
            suite = run_suite(
                ScenarioRunner(lambda _payload: {"ok": True}),
                collect_scenario_files(root),
                fail_fast=True,
            )
            self.assertEqual(suite["total"], 1)
            self.assertEqual(suite["scenarios"][0]["status"], "invalid")

    def test_empty_suite_directory_is_an_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ScenarioError, "No .*scenario.json"):
                collect_scenario_files(temp_dir)


if __name__ == "__main__":
    unittest.main()
