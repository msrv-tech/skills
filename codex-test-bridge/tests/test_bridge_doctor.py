import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_doctor import run_doctor


class BridgeDoctorTests(unittest.TestCase):
    def test_http_service_decodes_json_body_as_utf8_bytes(self):
        module = (Path(__file__).resolve().parents[1] / "src" / "HTTPServices" / "CodexTestBridge" / "Ext" / "Module.bsl").read_text(encoding="utf-8-sig")
        start = module.index("Функция ПрочитатьТелоJSON")
        end = module.index("КонецФункции", start)
        decoder = module[start:end]
        self.assertIn("ПолучитьСтрокуИзДвоичныхДанных", decoder)
        self.assertIn("Запрос.ПолучитьТелоКакДвоичныеДанные()", decoder)
        self.assertIn("КодировкаТекста.UTF8", decoder)

    def test_query_accepts_compatibility_alias(self):
        module = (Path(__file__).resolve().parents[1] / "src" / "HTTPServices" / "CodexTestBridge" / "Ext" / "Module.bsl").read_text(encoding="utf-8-sig")
        start = module.index("Функция КомандаQuery")
        end = module.index("КонецФункции", start)
        handler = module[start:end]
        self.assertIn('Получить(Данные, "text", "")', handler)
        self.assertIn('Получить(Данные, "query", "")', handler)

    def test_http_contract_without_worker(self):
        result = run_doctor(
            lambda: {"ok": True, "metadataName": "Demo"},
            lambda: {"ok": True, "contractVersion": 2, "variant": "full", "bridgeVersion": "0.2.0", "ui": {"worker": True}},
        )
        self.assertTrue(result["ok"])
        self.assertEqual([item["name"] for item in result["checks"]], ["http-health", "capabilities-v2"])
