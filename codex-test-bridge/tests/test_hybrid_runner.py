import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hybrid_runner import run_hybrid_scenario


class HybridRunnerTests(unittest.TestCase):
    def test_arrange_output_reaches_ui_and_created_object_is_cleaned(self):
        requests = []

        def send(request):
            requests.append(request)
            if request["command"] == "CreateCatalogItem":
                return {"ok": True, "ref": {"uuid": "00000000-0000-0000-0000-000000000001", "presentation": "Test"}}
            return {"ok": True}

        definition = {
            "name": "hybrid",
            "arrange": {"steps": [{"saveAs": "item", "request": {"command": "CreateCatalogItem", "catalog": "Items", "fields": {}}}]},
            "ui": {"steps": [{"action": "openNavigationLink", "kind": "catalog", "metadataName": "Items", "uuid": "${item.ref.uuid}"}]},
            "assert": {"steps": [{"request": {"command": "Health"}}]},
        }
        with tempfile.TemporaryDirectory() as temp, patch("hybrid_runner.run_ui_worker", return_value={"ok": True}):
            result = run_hybrid_scenario(definition, Path(temp) / "case.hybrid.json", send, {}, temp)
        self.assertTrue(result["ok"])
        self.assertEqual(requests[-1]["command"], "DeleteObject")
        self.assertEqual(requests[-1]["uuid"], "00000000-0000-0000-0000-000000000001")
