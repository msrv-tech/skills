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
    isolate_test_client_startup_parameter, resolve_native_ui_references, run_ui_worker,
    suppress_1c_startup_ui, validate_worker_config,
)
from agent_ui import diagnose_ui_failure, normalize_ui_tree
from uia_runner import _locate_inner_button_by_pixels
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
            "targetForm": {"formName": "Справочник.ВнутренниеДокументы.Форма.ФормаЭлемента"},
        }]})
        self.assertEqual(
            scenario["steps"][0]["link"],
            "e1cib/data/Справочник.ВнутренниеДокументы?ref=93f40050568b412711e40dada14919f5",
        )

    def test_navigation_requires_a_real_target_form(self):
        with self.assertRaisesRegex(UiWorkerError, "requires targetForm"):
            prepare_native_ui_scenario({"steps": [{"action": "openNavigationLink", "link": "e1cib/app/Обработка.Тест"}]})
        with self.assertRaisesRegex(UiWorkerError, "requires formName, objectName, or title"):
            prepare_native_ui_scenario({"steps": [{
                "action": "openNavigationLink", "link": "e1cib/app/Обработка.Тест", "targetForm": {"timeout": 10},
            }]})

    def test_open_data_processor_is_validated_without_a_manual_link(self):
        prepared = prepare_native_ui_scenario({"steps": [{
            "action": "openDataProcessor", "metadataName": "ЕМС_РабочееМестоМенеджера", "formName": "Форма",
            "targetForm": {"formName": "Обработка.ЕМС_РабочееМестоМенеджера.Форма.Форма"},
        }]})
        self.assertEqual(prepared["steps"][0]["metadataName"], "ЕМС_РабочееМестоМенеджера")
        with self.assertRaisesRegex(UiWorkerError, "requires metadataName"):
            prepare_native_ui_scenario({"steps": [{"action": "openDataProcessor", "targetForm": {"title": "Тест"}}]})

    def test_open_task_execution_form_requires_a_task_uuid(self):
        prepared = prepare_native_ui_scenario({"steps": [{
            "action": "openTaskExecutionForm", "metadataName": "ЗадачаИсполнителя", "uuid": "a14919f5-0dad-11e4-93f4-0050568b4127",
            "targetForm": {"formName": "БизнесПроцесс.Тест.Форма.Задача"},
        }]})
        self.assertEqual(prepared["steps"][0]["action"], "openTaskExecutionForm")
        with self.assertRaisesRegex(UiWorkerError, "requires uuid"):
            prepare_native_ui_scenario({"steps": [{"action": "openTaskExecutionForm", "targetForm": {"title": "Тест"}}]})
        with self.assertRaisesRegex(UiWorkerError, "requires metadataName"):
            prepare_native_ui_scenario({"steps": [{"action": "openTaskExecutionForm", "uuid": "a14919f5-0dad-11e4-93f4-0050568b4127", "targetForm": {"title": "Тест"}}]})

    def test_click_element_accepts_a_semantic_decoration_selector(self):
        prepared = prepare_native_ui_scenario({"steps": [{
            "action": "clickElement",
            "form": "taskCard",
            "elementType": "decoration",
            "element": {"title": "Перейти в форму для выполнения задачи"},
        }]})
        self.assertEqual(prepared["steps"][0]["elementType"], "decoration")

    def test_invalid_navigation_example_has_an_explicit_target(self):
        example = Path(__file__).resolve().parents[1] / "examples" / "invalid-navigation.ui.json"
        scenario = prepare_native_ui_scenario(json.loads(example.read_text(encoding="utf-8")))
        self.assertEqual(scenario["steps"][0]["targetForm"]["formName"], "Обработка.__CodexBridgeMissing__.Форма.Форма")

    def test_reference_uuid_is_resolved_to_choice_contract(self):
        scenario = prepare_native_ui_scenario({"steps": [{
            "action": "selectReference", "strategy": "choiceForm",
            "field": {"objectName": "Организация"}, "table": {"objectName": "Список"},
            "reference": {"kind": "catalog", "metadataName": "Организации", "uuid": "a14919f5-0dad-11e4-93f4-0050568b4127"},
        }]})
        resolved = resolve_native_ui_references(scenario, lambda request: {
            "ok": True, "ref": {"uuid": request["uuid"], "presentation": "Основная организация"},
        })
        step = resolved["steps"][0]
        self.assertNotIn("reference", step)
        self.assertEqual(step["value"], "Основная организация")
        self.assertEqual(step["row"], {"Наименование": "Основная организация"})
        self.assertTrue(step["strict"])

    def test_agent_ui_normalizes_tree_and_failure(self):
        normalized = normalize_ui_tree([
            {"level": 1, "type": "ТестируемаяТаблицаФормы", "name": "Товары", "title": "Товары"},
            {"level": 2, "type": "ТестируемоеПолеФормы", "name": "ТоварыКоличество", "title": "Количество"},
        ])
        self.assertEqual(normalized["tables"][0]["selector"], {"objectName": "Товары"})
        self.assertEqual(normalized["tables"][0]["columns"][0]["name"], "ТоварыКоличество")
        diagnosis = diagnose_ui_failure({"ok": False, "error": {"message": "UI object was not found"}})
        self.assertEqual(diagnosis["category"], "selector-not-found")

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
        self.assertIn("openDataProcessor", actions)

        self.assertIn("clickElement", actions)
        self.assertIn("clickCommandInterface", actions)
        self.assertIn("inspectTable", actions)
        self.assertIn("selectFromDropdown", actions)
        self.assertIn("openChoice", actions)
        self.assertIn("selectTableRow", actions)
        self.assertIn("expandTreeRow", actions)
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
        self.assertIn("expandParents", step["properties"])
        self.assertIn("replace", step["properties"])
        self.assertIn("uiaBeforeSteps", schema["properties"])
        self.assertIn("restartTestClientOnStartup", schema["properties"])
        self.assertFalse(schema["properties"]["restartTestClientOnStartup"]["default"])
        self.assertTrue(schema["properties"]["closeTestClientOnFinish"]["default"])

    def test_tree_row_expansion_contract_is_validated(self):
        scenario = prepare_native_ui_scenario({"steps": [{
            "action": "expandTreeRow", "table": {"objectName": "Дерево"},
            "row": {"Group": "Parent"},
        }, {
            "action": "selectTableRow", "table": {"objectName": "Дерево"},
            "expandParents": [{"Group": "Parent"}], "row": {"Item": "Child"},
        }]})
        self.assertEqual(scenario["steps"][1]["expandParents"][0]["Group"], "Parent")
        with self.assertRaisesRegex(UiWorkerError, "expandTreeRow requires row"):
            prepare_native_ui_scenario({"steps": [{"action": "expandTreeRow"}]})

    def test_command_interface_can_target_saved_form(self):
        scenario = prepare_native_ui_scenario({"steps": [{
            "action": "clickCommandInterface",
            "form": "workplace",
            "button": {"title": "Refresh"},
        }]})
        self.assertEqual(scenario["steps"][0]["form"], "workplace")
        module = (
            Path(__file__).resolve().parents[1]
            / "src" / "Ext" / "ManagedApplicationModule.bsl"
        ).read_text(encoding="utf-8-sig")
        self.assertIn("CTB_ОкноКомандногоИнтерфейса", module)
        self.assertIn("Форма.Активизировать()", module)

    def test_native_module_has_table_cell_editing_primitives(self):
        module = (
            Path(__file__).resolve().parents[1]
            / "src" / "Ext" / "ManagedApplicationModule.bsl"
        ).read_text(encoding="utf-8-sig")
        self.assertIn("Функция CTB_ПолучитьКонтекстПоля", module)
        self.assertIn("Таблица.ИзменитьСтроку()", module)
        self.assertIn("Поле.НачатьРедактированиеТекущейОбласти()", module)
        self.assertIn("КонтекстПоля.Поле.Выбрать()", module)
        self.assertIn("Таблица.ЗакончитьРедактированиеСтроки(Ложь)", module)
        self.assertIn("Таблица.ПолучитьТекстЯчейки", module)
        self.assertNotIn("commitActiveField", module)
        self.assertIn("CTB_НайтиКнопкуБезопасногоПерезапуска", module)
        self.assertIn('ЗакрытыеСтартовыеДиалоги.Найти("restartTestClient")', module)
        self.assertIn("CTB_ЗакрытьТестКлиентШтатно", module)
        self.assertIn("ТестКлиент.РазорватьСоединение()", module)
        self.assertIn("CTB_ОткрытьНавигационнуюЦель", module)
        self.assertIn("CTB_ПроверитьЧтоФормаНеОшибкаНавигации", module)

    def test_dialog_button_search_covers_message_box_containers(self):
        module = (
            Path(__file__).resolve().parents[1]
            / "src" / "Ext" / "ManagedApplicationModule.bsl"
        ).read_text(encoding="utf-8-sig")
        self.assertIn("Функция CTB_НайтиКнопкуДиалога", module)
        self.assertIn('Окно.ПолучитьКомандныйИнтерфейс()', module)
        self.assertIn('"ТестируемаяКнопкаКомандногоИнтерфейса"', module)

    def test_warm_suite_restores_test_client_after_server_hook(self):
        module = (
            Path(__file__).resolve().parents[1]
            / "src" / "Ext" / "ManagedApplicationModule.bsl"
        ).read_text(encoding="utf-8-sig")
        suite_start = module.index("Функция CTB_ВыполнитьНаборUIСценариев")
        suite_end = module.index("Функция CTB_ЗапроситьСервернуюФазуНабора", suite_start)
        suite = module[suite_start:suite_end]
        self.assertIn("CTB_ПереподключитьТестКлиентПослеСервернойФазы(ТестКлиент, Хост, Порт)", suite)
        self.assertLess(suite.index("CTB_ПереподключитьТестКлиентПослеСервернойФазы"), suite.index("CTB_ВыполнитьСценарий"))
        self.assertIn("ТестКлиент.РазорватьСоединение()", module)
        self.assertIn("ТестКлиент.УстановитьСоединение()", module)

    def test_server_hook_wait_releases_test_client_before_next_ui_scenario(self):
        module = (
            Path(__file__).resolve().parents[1]
            / "src" / "Ext" / "ManagedApplicationModule.bsl"
        ).read_text(encoding="utf-8-sig")
        start = module.index("Функция CTB_ЗапроситьСервернуюФазуНабора")
        end = module.index("Процедура CTB_ЗакрытьФормыСценария", start)
        hook = module[start:end]
        self.assertIn("CTB_ТекущийТестКлиент.РазорватьСоединение()", hook)
        self.assertNotIn("CTB_ПаузаТестКлиента(CTB_ТекущийТестКлиент)", hook)
        self.assertIn("CTB_ПереподключитьТестКлиентПослеСервернойФазы", module)
        self.assertIn('"opendataprocessor"', module)
        self.assertIn("CTB_ОбработатьКомандуОткрытияФормы", module)
        self.assertIn("ОткрытьФорму(ПолноеИмяФормы, ПараметрыОткрытия)", module)
        self.assertIn('Новый Структура("Ключ", ПолучитьИзВременногоХранилища(АдресСсылки))', module)
        self.assertIn("CTB_ЗапроситьUIAВызовЭлемента", module)
        self.assertIn('НРег(Строка(ВидЭлемента)) = "decoration"', module)
        self.assertIn("CTB_ОткрытьФормуЧерезТестКлиент", module)

    def test_uia_runner_has_visual_inner_button_fallback(self):
        runner = (Path(__file__).resolve().parents[1] / "uia_runner.py").read_text(encoding="utf-8")
        self.assertIn("def _capture_window_image", runner)
        self.assertIn("def _locate_inner_button_by_pixels", runner)
        self.assertIn("tableCellVisualInnerButton", runner)
        self.assertIn("PrintWindow", runner)

    def test_visual_inner_button_detector_prefers_right_field_button(self):
        from PIL import Image, ImageDraw

        class Rect:
            left = 10
            top = 20
            right = 210
            bottom = 50

        class WindowRect:
            left = 0
            top = 0

        image = Image.new("RGB", (240, 80), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((10, 20, 210, 50), outline=(170, 170, 170), fill=(250, 250, 250))
        draw.rectangle((182, 22, 207, 48), outline=(80, 80, 80), fill=(225, 225, 225))
        draw.ellipse((192, 33, 194, 35), fill=(30, 30, 30))
        draw.ellipse((197, 33, 199, 35), fill=(30, 30, 30))
        draw.ellipse((202, 33, 204, 35), fill=(30, 30, 30))

        match = _locate_inner_button_by_pixels(image, Rect(), WindowRect(), "choice")

        self.assertIsNotNone(match)
        assert match is not None
        self.assertGreaterEqual(match["screenPoint"]["x"], 180)
        self.assertLessEqual(match["screenPoint"]["x"], 210)

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

    def test_test_client_startup_parameter_is_isolated(self):
        command = isolate_test_client_startup_parameter(["1cv8c", "ENTERPRISE", "/TestClient", "-TPort", "1538"])
        self.assertIn("/CTemp", command)
        self.assertLess(command.index("/CTemp"), command.index("/TestClient"))
        self.assertEqual(command.count("/CTemp"), 1)
        self.assertEqual(isolate_test_client_startup_parameter(command), command)
        self.assertEqual(isolate_test_client_startup_parameter(["python", "client.py"]), ["python", "client.py"])

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
