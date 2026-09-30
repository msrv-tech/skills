import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
CLIENT_MODULE = ROOT / "src" / "Ext" / "ManagedApplicationModule.bsl"
SERVER_MODULE = ROOT / "src" / "CommonModules" / "CodexUIJobsServer" / "Ext" / "Module.bsl"
RUNNER = ROOT / "scripts" / "run_web_client_compile_smoke.py"
SPEC = importlib.util.spec_from_file_location("run_web_client_compile_smoke", RUNNER)
WEB_SMOKE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(WEB_SMOKE)


class WebClientCompatibilityTests(unittest.TestCase):
    def test_managed_application_module_delegates_json_to_server(self):
        client = CLIENT_MODULE.read_text(encoding="utf-8-sig")

        self.assertIn(
            "CodexUIJobsServer.ПрочитатьJSONСервер(Текст)",
            client,
        )
        self.assertIn(
            "CodexUIJobsServer.ЗаписатьJSONСервер(Данные)",
            client,
        )
        self.assertNotIn("Новый ЧтениеJSON", client)
        self.assertNotIn("Новый ЗаписьJSON", client)
        self.assertIsNone(re.search(r"(?<![\w])ПрочитатьJSON\(", client))
        self.assertIsNone(re.search(r"(?<![\w])ЗаписатьJSON\(", client))

    def test_server_module_owns_json_round_trip_with_correspondence(self):
        server = SERVER_MODULE.read_text(encoding="utf-8-sig")

        self.assertRegex(server, r"Функция ПрочитатьJSONСервер\(Текст\) Экспорт")
        self.assertIn("Возврат ПрочитатьJSON(Чтение, Истина);", server)
        self.assertRegex(server, r"Функция ЗаписатьJSONСервер\(Данные\) Экспорт")
        self.assertIn("ЗаписатьJSON(Запись, Данные);", server)

    def test_web_smoke_uses_only_registered_database_credentials(self):
        database = {
            "path": "/projects/demo",
            "Ref": "demo-ref",
            "User": "registered-user",
            "Password": "private-password",
            "Bridge": {
                "AppName": "demo-app",
                "BaseUrl": "https://example.invalid/demo/hs/codex-test",
            },
        }
        self.assertIs(database, WEB_SMOKE.select_database([database], "demo-app"))
        self.assertEqual("https://example.invalid/demo", WEB_SMOKE.registered_web_url(database))

        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "registry.json"
            registry.write_text(
                json.dumps({"databases": [database]}), encoding="utf-8",
            )
            with patch.object(WEB_SMOKE.subprocess, "run") as run:
                run.return_value.returncode = 0
                result = WEB_SMOKE.main([
                    "--registry", str(registry), "--database", "demo-ref",
                ])

        self.assertEqual(0, result)
        command = run.call_args.args[0]
        environment = run.call_args.kwargs["env"]
        self.assertNotIn("registered-user", command)
        self.assertNotIn("private-password", command)
        self.assertEqual("registered-user", environment["CODEX_1C_USERNAME"])
        self.assertEqual("private-password", environment["CODEX_1C_PASSWORD"])


if __name__ == "__main__":
    unittest.main()
