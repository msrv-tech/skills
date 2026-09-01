import json
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ui_worker import (
    UiWorkerError, expand, navigation_ref_from_uuid, prepare_native_ui_scenario, redact_command,
    run_ui_worker, suppress_1c_startup_ui, validate_worker_config,
)
from client import compact_ui_result


CLIENT_CODE = """
import socket, sys, time
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('127.0.0.1', int(sys.argv[1])))
s.listen(5)
while True:
    time.sleep(0.1)
"""

MANAGER_CODE = """
import json, sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps({'ok': True, 'tests': 1}), encoding='utf-8')
"""


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class UiWorkerTests(unittest.TestCase):
    def test_compact_ui_result_does_not_embed_ui_tree(self):
        compact = compact_ui_result({
            "ok": True, "runId": "run", "status": "passed", "durationMs": 42,
            "managerResult": {"steps": [{"status": "passed", "actual": [{"huge": "tree"}]}]},
            "artifacts": {"summary": "summary.json"},
        })
        self.assertEqual(compact["steps"], 1)
        self.assertEqual(compact["failedSteps"], 0)
        self.assertNotIn("managerResult", compact)
        self.assertNotIn("tree", json.dumps(compact))
    def test_navigation_ref_uses_1c_group_order(self):
        self.assertEqual(
            navigation_ref_from_uuid("a14919f5-0dad-11e4-93f4-0050568b4127"),
            "93f40050568b412711e40dada14919f5",
        )

    def test_navigation_uuid_shorthand_is_expanded_before_start(self):
        scenario = prepare_native_ui_scenario({"steps": [{
            "action": "openNavigationLink", "kind": "catalog", "metadataName": "ВнутренниеДокументы",
            "uuid": "a14919f5-0dad-11e4-93f4-0050568b4127",
        }]})
        self.assertEqual(
            scenario["steps"][0]["link"],
            "e1cib/data/Справочник.ВнутренниеДокументы?ref=93f40050568b412711e40dada14919f5",
        )

    def test_invalid_native_scenario_is_rejected_before_start(self):
        with self.assertRaisesRegex(UiWorkerError, "non-empty array"):
            prepare_native_ui_scenario({"steps": []})
        with self.assertRaisesRegex(UiWorkerError, "unsupported action"):
            prepare_native_ui_scenario({"steps": [{"action": "magic"}]})
        with self.assertRaisesRegex(UiWorkerError, "unknown fields: typo"):
            prepare_native_ui_scenario({"steps": [{"action": "assertConnected", "typo": True}]})

    def test_native_ui_schema_exposes_reference_actions(self):
        schema_path = Path(__file__).resolve().parents[1] / "ui-scenario.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        step = schema["$defs"]["step"]
        actions = step["properties"]["action"]["enum"]

        self.assertIn("selectReference", actions)
        self.assertIn("inspectUI", actions)
        self.assertIn("openNavigationLink", actions)
        self.assertIn("inspectTable", actions)
        self.assertIn("selectFromDropdown", actions)
        self.assertIn("openChoice", actions)
        self.assertIn("selectTableRow", actions)
        self.assertIn("waitElement", actions)
        self.assertIn("assertElement", actions)
        self.assertIn("setCheckbox", actions)
        self.assertIn("assertTableRow", actions)
        self.assertIn("inputTableCell", actions)
        self.assertIn("handleDialog", actions)
        self.assertIn("waitFormClosed", actions)
        self.assertEqual(
            step["properties"]["strategy"]["enum"],
            ["auto", "dropdownExact", "typeAhead", "choiceForm"],
        )
        self.assertIn("formName", schema["$defs"]["selector"]["properties"])
        self.assertIn("choiceTable", step["properties"])
        self.assertIn("choiceRow", step["properties"])
        self.assertIn("onChangeWait", step["properties"])
        self.assertIn("replace", step["properties"])
        self.assertIn("uiaBeforeSteps", schema["properties"])

    def test_native_module_has_table_cell_editing_primitives(self):
        module = (
            Path(__file__).resolve().parents[1]
            / "src" / "Ext" / "ManagedApplicationModule.bsl"
        ).read_text(encoding="utf-8-sig")
        self.assertIn("Функция CTB_ПолучитьКонтекстПоля", module)
        self.assertIn("Таблица.ИзменитьСтроку()", module)
        self.assertIn("Таблица.ЗакончитьРедактированиеСтроки(Ложь)", module)
        self.assertIn("Таблица.ПолучитьТекстЯчейки", module)

    def test_expand_and_unknown_placeholder(self):
        self.assertEqual(expand(["-TPort{testPort}"], {"testPort": "1538"}), ["-TPort1538"])
        with self.assertRaisesRegex(UiWorkerError, "Unknown command placeholder"):
            expand("{missing}", {})

    def test_config_validation(self):
        with self.assertRaisesRegex(UiWorkerError, "clientCommand"):
            validate_worker_config({"managerCommand": ["manager"]})
        with self.assertRaisesRegex(UiWorkerError, "Unsupported UI backend"):
            validate_worker_config({"backend": "screen", "clientCommand": ["a"], "managerCommand": ["b"]})
        with self.assertRaisesRegex(UiWorkerError, "bridgeBaseUrl"):
            validate_worker_config({"resultTransport": "bridgeJob", "clientCommand": ["a"], "managerCommand": ["b"]})

    def test_password_is_redacted_from_report_command(self):
        command = ["1cv8c.exe", "/N", "Tester", "/P", "secret", "/TestClient"]
        self.assertEqual(redact_command(command, ["/P"])[4], "***")
        self.assertEqual(command[4], "secret")

    def test_connection_and_login_are_always_redacted(self):
        command = ["1cv8c", "ENTERPRISE", "/S", "server\\database", "/N", "user", "/Psecret"]
        redacted = redact_command(command, [])
        self.assertEqual(redacted[3], "***")
        self.assertEqual(redacted[5], "***")
        self.assertEqual(redacted[6], "/P***")
        self.assertNotIn("server\\database", redacted)
        self.assertNotIn("user", redacted)

    def test_test_client_and_manager_suppress_startup_ui_by_default(self):
        command = suppress_1c_startup_ui(["1cv8c", "ENTERPRISE", "/TestClient", "-TPort", "1538"])
        self.assertIn("/DisableStartupDialogs", command)
        self.assertIn("/DisableStartupMessages", command)
        self.assertIn("/DisableSplash", command)
        self.assertLess(command.index("/DisableSplash"), command.index("/TestClient"))
        self.assertEqual(command.count("/DisableSplash"), 1)

        unchanged = suppress_1c_startup_ui(["python", "manager.py"])
        self.assertEqual(unchanged, ["python", "manager.py"])

    def test_redacted_command_is_safe_to_serialize_in_report(self):
        command = ["1cv8c", "ENTERPRISE", "/F", "private-database-path", "/N", "private-login", "/P", "private-password"]
        serialized = json.dumps({"command": redact_command(command, [])})
        self.assertNotIn("private-database-path", serialized)
        self.assertNotIn("private-login", serialized)
        self.assertNotIn("private-password", serialized)

    def test_environment_placeholder_is_required(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            scenario = root / "ui.json"
            scenario.write_text('{"steps":[{"action":"assertConnected"}]}', encoding="utf-8")
            config = {
                "backend": "process",
                "environmentPlaceholders": {"password": "MISSING_CODEX_TEST_PASSWORD"},
                "clientCommand": ["client", "/P", "{password}"],
                "managerCommand": ["manager"],
            }
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("MISSING_CODEX_TEST_PASSWORD", None)
                with self.assertRaisesRegex(UiWorkerError, "MISSING_CODEX_TEST_PASSWORD"):
                    run_ui_worker(config, scenario, root / "artifacts")

    def test_process_backend_runs_client_and_manager(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            scenario = root / "ui.feature"
            scenario.write_text("smoke", encoding="utf-8")
            port = free_port()
            config = {
                "backend": "process",
                "testPort": port,
                "startupTimeoutSeconds": 5,
                "probeTestPort": True,
                "timeoutSeconds": 5,
                "clientCommand": [sys.executable, "-c", CLIENT_CODE, "{testPort}"],
                "managerCommand": [sys.executable, "-c", MANAGER_CODE, "{artifactDir}/manager-result.json"],
                "resultFile": "{artifactDir}/manager-result.json",
            }

            report = run_ui_worker(config, scenario, root / "artifacts")

            self.assertTrue(report["ok"])
            self.assertEqual(report["backend"], "process")
            self.assertEqual(report["managerResult"]["tests"], 1)
            self.assertEqual(report["manager"]["exitCode"], 0)
            summary = json.loads((root / "artifacts" / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["runId"], report["runId"])

    def test_worker_replaces_stale_summary_at_start(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            (artifacts / "summary.json").write_text('{"runId":"previous"}', encoding="utf-8")
            scenario = root / "missing.json"
            config = {"backend": "process", "clientCommand": ["client"], "managerCommand": ["manager"]}
            with self.assertRaisesRegex(UiWorkerError, "does not exist"):
                run_ui_worker(config, scenario, artifacts)
            summary = json.loads((artifacts / "summary.json").read_text(encoding="utf-8"))
            self.assertNotEqual(summary["runId"], "previous")
            self.assertEqual(summary["status"], "starting")

    def test_bridge_job_transport_queues_and_reads_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            scenario = root / "ui.json"
            scenario.write_text('{"$schema":"../ui-scenario.schema.json","name":"smoke","steps":[{"action":"assertConnected"}]}', encoding="utf-8")
            port = free_port()
            config = {
                "backend": "process",
                "bridgeBaseUrl": "http://bridge.invalid/hs/codex-test",
                "resultTransport": "bridgeJob",
                "testPort": port,
                "probeTestPort": True,
                "startupTimeoutSeconds": 5,
                "timeoutSeconds": 5,
                "clientCommand": [sys.executable, "-c", CLIENT_CODE, "{testPort}"],
                "managerCommand": [sys.executable, "-c", "pass", "{jobId}"],
            }
            calls = []

            def fake_bridge(_config, payload):
                calls.append(payload)
                if payload["command"] == "uiJobGet":
                    return {"status": "passed", "result": json.dumps({"ok": True, "tests": 1})}
                return {"ok": True}

            with patch("ui_worker.bridge_command", side_effect=fake_bridge):
                report = run_ui_worker(config, scenario, root / "artifacts")

            self.assertTrue(report["ok"], report)
            self.assertEqual(report["resultTransport"], "bridgeJob")
            self.assertEqual(report["managerResult"]["tests"], 1)
            commands = [call["command"] for call in calls]
            self.assertEqual(commands[0], "uiJobCreate")
            self.assertEqual(commands[-1], "uiJobDelete")
            self.assertGreaterEqual(commands.count("uiJobGet"), 1)
            self.assertEqual(calls[0]["jobId"], report["jobId"])
            self.assertNotIn("$schema", calls[0]["scenario"])
            self.assertTrue(Path(report["artifacts"]["progress"]).is_file())
            self.assertTrue(Path(report["artifacts"]["summary"]).is_file())

    def test_inline_log_transport_embeds_scenario_and_reads_marker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            scenario = root / "ui.json"
            scenario.write_text('{"name":"inline smoke","steps":[{"action":"assertConnected"}]}', encoding="utf-8")
            port = free_port()
            manager_code = (
                "import base64,json,sys;"
                "scenario=json.loads(base64.b64decode(sys.argv[2]).decode('ascii'));"
                "open(sys.argv[1],'w',encoding='utf-8').write("
                "'message CODEX_UI_RESULT:'+json.dumps({'ok':True,'name':scenario['name']})+' trailing')"
            )
            config = {
                "backend": "process",
                "resultTransport": "inlineLog",
                "testPort": port,
                "probeTestPort": True,
                "startupTimeoutSeconds": 5,
                "timeoutSeconds": 5,
                "clientCommand": [sys.executable, "-c", CLIENT_CODE, "{testPort}"],
                "managerCommand": [sys.executable, "-c", manager_code, "{managerLog}", "{scenarioBase64}"],
            }

            report = run_ui_worker(config, scenario, root / "artifacts")

            self.assertTrue(report["ok"], report)
            self.assertEqual(report["resultTransport"], "inlineLog")
            self.assertEqual(report["managerResult"]["name"], "inline smoke")
            self.assertTrue(Path(report["managerLog"]).is_file())

    def test_missing_scenario_is_rejected_before_process_start(self):
        config = {"backend": "process", "clientCommand": ["client"], "managerCommand": ["manager"]}
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(UiWorkerError, "does not exist"):
                run_ui_worker(config, Path(temp_dir) / "missing.feature", Path(temp_dir) / "artifacts")

    @unittest.skipUnless(os.name == "nt", "Windows hidden desktop test")
    def test_windows_hidden_desktop_backend(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            scenario = root / "ui.feature"
            scenario.write_text("smoke", encoding="utf-8")
            config = {
                "backend": "windowsDesktop",
                "testPort": free_port(),
                "startupTimeoutSeconds": 5,
                "probeTestPort": True,
                "timeoutSeconds": 5,
                "clientCommand": [sys.executable, "-c", CLIENT_CODE, "{testPort}"],
                "managerCommand": [sys.executable, "-c", MANAGER_CODE, "{artifactDir}/manager-result.json"],
                "resultFile": "{artifactDir}/manager-result.json",
            }
            report = run_ui_worker(config, scenario, root / "artifacts")
            self.assertTrue(report["ok"], report)
            self.assertEqual(report["backend"], "windowsDesktop")


if __name__ == "__main__":
    unittest.main()
