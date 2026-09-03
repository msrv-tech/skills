import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_doctor import run_doctor


class BridgeDoctorTests(unittest.TestCase):
    def test_http_contract_without_worker(self):
        result = run_doctor(
            lambda: {"ok": True, "metadataName": "Demo"},
            lambda: {"ok": True, "contractVersion": 2, "variant": "full", "bridgeVersion": "0.2.0", "ui": {"worker": True}},
        )
        self.assertTrue(result["ok"])
        self.assertEqual([item["name"] for item in result["checks"]], ["http-health", "capabilities-v2"])
